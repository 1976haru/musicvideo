from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from .editor import check_readiness, probe_media
from .reference_vault import resolve_reference_path
from .result_takes import GenerationTake, audit_take_state, resolve_take_path
from .semantic_qc import adjacent_visual_findings
from .story_engine import (
    cinematic_warnings,
    duplicate_id_warnings,
    literalization_warnings,
    motif_progression_warnings,
    shot_timeline_warnings,
    timeline_warnings,
)

if TYPE_CHECKING:
    from .models import ShotSpec
    from .session import LyricsWorldSession


PRODUCTION_ORCHESTRATOR_VERSION = "g9-1"
GenerationAdapter = Literal["MANUAL", "COMFYUI_LOCAL"]
JobStatus = Literal["PENDING", "RUNNING", "DONE", "FAILED", "CANCELLED"]
ReadinessStatus = Literal["READY", "READY_WITH_WARNINGS", "BLOCKED", "NOT_STARTED"]


class ProductionIssue(BaseModel):
    code: str
    severity: Literal["blocker", "warning", "info"]
    stage_id: str
    message: str
    action: str = ""
    shot_id: str | None = None
    episode_id: str | None = None


class ProductionStageStatus(BaseModel):
    stage_id: str
    label: str
    status: ReadinessStatus
    ready_count: int = 0
    total_count: int = 0
    issues: list[ProductionIssue] = Field(default_factory=list)


class ShotProductionStatus(BaseModel):
    shot_id: str
    episode_id: str | None = None
    pack_id: str | None = None
    pack_ready: bool = False
    contract_hash: str = ""
    stale_pack: bool = False
    accepted_take_id: str | None = None
    technical_qc_status: str = "MISSING"
    semantic_qc_status: str = "MISSING"
    issues: list[ProductionIssue] = Field(default_factory=list)


class ProductionReadinessReport(BaseModel):
    report_version: str = PRODUCTION_ORCHESTRATOR_VERSION
    created_at: str
    status: Literal["READY", "READY_WITH_WARNINGS", "BLOCKED"]
    stages: list[ProductionStageStatus] = Field(default_factory=list)
    shots: list[ShotProductionStatus] = Field(default_factory=list)
    blockers: int = 0
    warnings: int = 0
    next_actions: list[str] = Field(default_factory=list)

    def stage(self, stage_id: str) -> ProductionStageStatus | None:
        return next((stage for stage in self.stages if stage.stage_id == stage_id), None)


class ShotContinuityContract(BaseModel):
    contract_id: str
    contract_hash: str
    shot_id: str
    episode_id: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    variant_ids: list[str] = Field(default_factory=list)
    world_locks: list[str] = Field(default_factory=list)
    entity_locks: list[str] = Field(default_factory=list)
    visual_locks: list[str] = Field(default_factory=list)
    transition_in: list[str] = Field(default_factory=list)
    transition_out: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    reference_paths: list[str] = Field(default_factory=list)
    series_asset_ids: list[str] = Field(default_factory=list)
    series_asset_paths: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def prompt_block(self) -> str:
        sections = [
            "CONTINUITY CONTRACT — DO NOT BREAK",
            f"Shot: {self.shot_id}",
            f"Episode: {self.episode_id or 'single/project'}",
        ]
        if self.world_locks:
            sections.append("WORLD LOCKS: " + " | ".join(self.world_locks))
        if self.entity_locks:
            sections.append("ENTITY HARD LOCKS: " + " | ".join(self.entity_locks))
        if self.visual_locks:
            sections.append("VISUAL LOCKS: " + " | ".join(self.visual_locks))
        if self.transition_in:
            sections.append("CONTINUITY IN: " + " | ".join(self.transition_in))
        if self.transition_out:
            sections.append("CONTINUITY OUT: " + " | ".join(self.transition_out))
        if self.negative_constraints:
            sections.append("NEVER INTRODUCE: " + " | ".join(self.negative_constraints))
        sections.append(
            "FINAL VERIFICATION: preserve identity topology, locked counts, negative space, geography, "
            "prop state, light direction, and transition state over spectacle."
        )
        return "\n".join(sections)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value).split())
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _portable_resolve(path: str | Path, project_dir: str | Path | None) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and project_dir:
        candidate = Path(project_dir) / candidate
    return candidate.resolve(strict=False)


def _contract_payload(contract: ShotContinuityContract) -> dict[str, Any]:
    data = contract.model_dump(mode="json")
    data.pop("contract_hash", None)
    data.pop("contract_id", None)
    return data


def _contract_hash(contract: ShotContinuityContract) -> str:
    payload = json.dumps(_contract_payload(contract), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compile_shot_continuity_contract(session: LyricsWorldSession, shot: ShotSpec) -> ShotContinuityContract:
    """Compile all immutable/continuity evidence that should survive prompt rewrites.

    This function is deterministic and side-effect free. It does not generate images,
    download models, mutate session state, or write files.
    """
    bible = session.world_bible
    series = session.series_bible
    entity_map = {entity.entity_id: entity for entity in session.series_entities}
    ref_map = {asset.reference_id: asset for asset in session.references}

    world_locks: list[str] = []
    visual_locks: list[str] = []
    negatives: list[str] = list(shot.negative_constraints)
    blockers: list[str] = []
    warnings: list[str] = []

    if bible:
        world_locks.extend([
            bible.premise,
            bible.emotional_thesis,
            *bible.reality_rules,
            *bible.weather_rules,
        ])
        visual_locks.extend([
            *bible.visual_language,
            *bible.palette,
            *bible.material_language,
            *bible.lighting_rules,
            *bible.camera_rules,
        ])
        negatives.extend(bible.forbidden_elements)
    else:
        warnings.append("World Bible is not available.")

    if series:
        world_locks.extend(series.common_world_rules)
        visual_locks.extend(series.common_visual_rules)
        negatives.extend(series.forbidden_elements)

    entity_locks: list[str] = []
    for entity_id in shot.series_entity_ids:
        entity = entity_map.get(entity_id)
        if not entity:
            blockers.append(f"Unknown Series Entity: {entity_id}")
            continue
        if shot.series_episode_id and entity.episode_presence and shot.series_episode_id not in entity.episode_presence:
            warnings.append(f"{entity_id} is not registered for {shot.series_episode_id}.")
        entity_locks.append(
            f"{entity.entity_id}: TEXT MASTER={entity.text_master}; "
            f"LOCKED PARTS={'; '.join(entity.shape_grammar.locked_parts)}; "
            f"SHAPE={'; '.join(entity.shape_grammar.silhouette_rules)}; "
            f"PALETTE={'; '.join(entity.palette_rules)}; "
            f"MOTION={'; '.join(entity.motion_rules)}"
        )
        negatives.extend(entity.forbidden_rules)
        negatives.extend(entity.shape_grammar.forbidden_mutations)
        applied_variants = [
            variant for variant in entity.variants
            if variant.variant_id in shot.series_variant_ids
            or (
                variant.kind == "episode"
                and shot.series_episode_id
                and variant.episode_id == shot.series_episode_id
            )
        ]
        for variant in applied_variants:
            chunks = [
                *variant.appearance_delta,
                *variant.palette_delta,
                *variant.motion_delta,
            ]
            if chunks:
                entity_locks.append(f"{entity.entity_id} VARIANT {variant.variant_id}: {'; '.join(chunks)}")

    known_variants = {
        variant.variant_id
        for entity_id in shot.series_entity_ids
        for entity in [entity_map.get(entity_id)]
        if entity
        for variant in entity.variants
    }
    unknown_variants = [variant_id for variant_id in shot.series_variant_ids if variant_id not in known_variants]
    if unknown_variants:
        blockers.append("Unknown Series Variant(s): " + ", ".join(unknown_variants))

    reference_ids: list[str] = []
    reference_paths: list[str] = []
    for reference_id in shot.reference_ids:
        asset = ref_map.get(reference_id)
        if not asset:
            blockers.append(f"Unknown Reference ID: {reference_id}")
            continue
        path = resolve_reference_path(asset, session.project_dir)
        reference_ids.append(reference_id)
        reference_paths.append(str(path))
        if not path.is_file():
            blockers.append(f"Missing reference file: {reference_id}")

    series_asset_ids: list[str] = []
    series_asset_paths: list[str] = []
    for asset in session.series_assets:
        if asset.review_status != "approved":
            continue
        if asset.entity_id and asset.entity_id not in shot.series_entity_ids:
            continue
        if asset.episode_id and shot.series_episode_id and asset.episode_id != shot.series_episode_id:
            continue
        path = _portable_resolve(asset.path, session.project_dir)
        series_asset_ids.append(asset.asset_id)
        series_asset_paths.append(str(path))
        if not path.is_file():
            blockers.append(f"Missing approved Series Asset: {asset.asset_id}")

    contract = ShotContinuityContract(
        contract_id=f"CONTRACT-{shot.shot_id}",
        contract_hash="",
        shot_id=shot.shot_id,
        episode_id=shot.series_episode_id,
        entity_ids=list(shot.series_entity_ids),
        variant_ids=list(shot.series_variant_ids),
        world_locks=_dedupe(world_locks),
        entity_locks=_dedupe(entity_locks),
        visual_locks=_dedupe(visual_locks),
        transition_in=_dedupe(list(shot.continuity_in)),
        transition_out=_dedupe(list(shot.continuity_out)),
        negative_constraints=_dedupe(negatives),
        reference_ids=_dedupe(reference_ids),
        reference_paths=_dedupe(reference_paths),
        series_asset_ids=_dedupe(series_asset_ids),
        series_asset_paths=_dedupe(series_asset_paths),
        blockers=_dedupe(blockers),
        warnings=_dedupe(warnings),
    )
    contract.contract_hash = _contract_hash(contract)
    return contract


def _latest_pack(session: LyricsWorldSession, shot_id: str):
    candidates = [pack for pack in session.generation_packs if pack.shot_id == shot_id]
    return max(candidates, key=lambda pack: (pack.created_at, pack.pack_id)) if candidates else None


def _accepted_take(session: LyricsWorldSession, shot_id: str) -> GenerationTake | None:
    accepted = [take for take in session.generation_takes if take.shot_id == shot_id and take.status == "accepted"]
    return accepted[0] if len(accepted) == 1 else None


def _latest_qc(session: LyricsWorldSession, take_id: str):
    reports = [report for report in session.qc_reports if report.take_id == take_id]
    return reports[-1] if reports else None


def _semantic_status(session: LyricsWorldSession, take_id: str) -> str:
    reports = [report for report in session.semantic_qc_reports if report.take_id == take_id]
    if not reports:
        return "MISSING"
    report = reports[-1]
    statuses = {finding.status for finding in report.findings}
    if "REGENERATE" in statuses or "BLOCKED" in statuses:
        return "REGENERATE"
    if "REVIEW" in statuses:
        return "REVIEW"
    return "PASS"


def _stage(stage_id: str, label: str, issues: list[ProductionIssue], ready: int = 0, total: int = 0) -> ProductionStageStatus:
    if total == 0 and not issues:
        status: ReadinessStatus = "NOT_STARTED"
    elif any(issue.severity == "blocker" for issue in issues):
        status = "BLOCKED"
    elif issues:
        status = "READY_WITH_WARNINGS"
    else:
        status = "READY"
    return ProductionStageStatus(
        stage_id=stage_id,
        label=label,
        status=status,
        ready_count=ready,
        total_count=total,
        issues=issues,
    )


def build_production_readiness(session: LyricsWorldSession) -> ProductionReadinessReport:
    """Strict preflight across the whole MV pipeline.

    Missing optional semantic AI stays a warning, while missing accepted media, stale
    prompt contracts, broken references, timeline overlaps, or failed technical QC are
    blockers for a final-ready project.
    """
    stages: list[ProductionStageStatus] = []
    shot_states: list[ShotProductionStatus] = []

    # 01 Music
    issues: list[ProductionIssue] = []
    music_path = _portable_resolve(session.music_path, session.project_dir) if session.music_path else None
    if not session.music_path:
        issues.append(ProductionIssue(code="NO_MUSIC", severity="blocker", stage_id="music", message="음악 파일이 없습니다.", action="01 MUSIC에서 음악 파일 선택"))
    elif not music_path or not music_path.is_file():
        issues.append(ProductionIssue(code="MISSING_MUSIC", severity="blocker", stage_id="music", message="음악 파일 경로가 끊어졌습니다.", action="음악 파일 다시 연결"))
    if session.music_path and not session.audio_map:
        issues.append(ProductionIssue(code="NO_AUDIO_MAP", severity="blocker", stage_id="music", message="음악 분석 결과가 없습니다.", action="음악 분석 + MV Timeline 생성"))
    stages.append(_stage("music", "01 MUSIC", issues, 1 if session.audio_map else 0, 1))

    # 02 Lyrics/World
    issues = []
    if not session.lines or not session.analysis:
        issues.append(ProductionIssue(code="NO_LYRIC_ANALYSIS", severity="blocker", stage_id="world", message="가사 분석이 완료되지 않았습니다.", action="02 LYRICS & MEANING에서 분석"))
    if not session.world_bible:
        issues.append(ProductionIssue(code="NO_WORLD_BIBLE", severity="blocker", stage_id="world", message="World Bible이 없습니다.", action="04 WORLD BIBLE에서 전체 초안 생성"))
    else:
        editable = (
            "premise", "emotional_thesis", "reality_rules", "time_period", "visual_language",
            "palette", "material_language", "weather_rules", "lighting_rules", "camera_rules",
            "recurring_motifs", "forbidden_elements",
        )
        missing = [name for name in editable if not getattr(session.world_bible, name)]
        if missing:
            issues.append(ProductionIssue(code="INCOMPLETE_WORLD_BIBLE", severity="blocker", stage_id="world", message=f"World Bible 빈 필드 {len(missing)}개", action="World Bible 빈 항목 자동 보강"))
    stages.append(_stage("world", "02–04 LYRICS / WORLD", issues, 1 if session.world_bible else 0, 1))

    # Series/reference state.
    issues = []
    if session.series_bible:
        if not session.series_entities:
            issues.append(ProductionIssue(code="NO_SERIES_ENTITIES", severity="blocker", stage_id="series", message="Series Bible은 있지만 Entity Registry가 비어 있습니다.", action="SERIES STUDIO seed/Registry 확인"))
        for asset in session.series_assets:
            if asset.review_status == "approved" and not _portable_resolve(asset.path, session.project_dir).is_file():
                issues.append(ProductionIssue(code="MISSING_SERIES_ASSET", severity="blocker", stage_id="series", message=f"승인 Series Asset 파일 누락: {asset.asset_id}", action="Assets에서 다시 연결"))
    if session.shots and not session.references and not session.series_assets:
        issues.append(ProductionIssue(code="NO_VISUAL_REFERENCES", severity="warning", stage_id="series", message="Shot은 있지만 이미지 레퍼런스가 하나도 없습니다.", action="Reference Director/Text Master/Reference Vault 확인"))
    stages.append(_stage(
        "series",
        "SERIES / REFERENCES",
        issues,
        sum(1 for asset in session.series_assets if asset.review_status == "approved") + len(session.references),
        len(session.series_assets) + len(session.references),
    ))

    # Story and shot structure.
    issues = []
    if not session.story_beats:
        issues.append(ProductionIssue(code="NO_STORY_BEATS", severity="blocker", stage_id="story", message="Story Beat가 없습니다.", action="06 STORY ROOM에서 Story Beat 생성/작성"))
    for warning in duplicate_id_warnings(session.story_beats, session.shots):
        issues.append(ProductionIssue(code=warning.code.upper(), severity="blocker", stage_id="story", message=warning.message))
    for warning in timeline_warnings(session.story_beats, session.duration_sec):
        severity = "blocker" if warning.code in {"overlap"} else "warning"
        issues.append(ProductionIssue(code=warning.code.upper(), severity=severity, stage_id="story", message=warning.message))
    for warning in motif_progression_warnings(session.story_beats):
        issues.append(ProductionIssue(code=warning.code.upper(), severity="warning", stage_id="story", message=warning.message))
    stages.append(_stage("story", "06 STORY ROOM", issues, len(session.story_beats), len(session.story_beats)))

    issues = []
    if not session.shots:
        issues.append(ProductionIssue(code="NO_SHOTS", severity="blocker", stage_id="shots", message="Shot이 없습니다.", action="07 SHOT BOARD에서 Shot 생성"))
    for warning in shot_timeline_warnings(session.story_beats, session.shots):
        severity = "blocker" if warning.code in {"shot_overlap", "invalid_beat_id"} else "warning"
        issues.append(ProductionIssue(code=warning.code.upper(), severity=severity, stage_id="shots", message=warning.message))
    lyric_map = {line.line_id: line.text for line in session.lines}
    for warning in cinematic_warnings(session.shots):
        issues.append(ProductionIssue(code=warning.code.upper(), severity="warning", stage_id="shots", message=warning.message))
    for warning in literalization_warnings(session.shots, lyric_map):
        issues.append(ProductionIssue(code=warning.code.upper(), severity="warning", stage_id="shots", message=warning.message))
    stages.append(_stage("shots", "07 SHOT BOARD", issues, len(session.shots), len(session.shots)))

    # Prompt/take/QC state per shot.
    prompt_issues: list[ProductionIssue] = []
    take_issues: list[ProductionIssue] = []
    qc_issues: list[ProductionIssue] = []
    accepted_count = 0
    pack_ready_count = 0
    qc_ready_count = 0
    technical_by_take: dict[str, str] = {}

    take_audit = audit_take_state(
        session.generation_takes,
        session.shots,
        session.generation_packs,
        session.project_dir,
        session.take_id_counters,
    )
    for warning in take_audit:
        take_issues.append(ProductionIssue(code=warning.code, severity="blocker", stage_id="takes", message=warning.message))

    for shot in sorted(session.shots, key=lambda item: (item.start_sec, item.shot_id)):
        state = ShotProductionStatus(shot_id=shot.shot_id, episode_id=shot.series_episode_id)
        contract = compile_shot_continuity_contract(session, shot)
        state.contract_hash = contract.contract_hash
        for blocker in contract.blockers:
            issue = ProductionIssue(code="CONTRACT_BLOCKER", severity="blocker", stage_id="prompts", message=blocker, shot_id=shot.shot_id, episode_id=shot.series_episode_id)
            state.issues.append(issue)
            prompt_issues.append(issue)
        for warning in contract.warnings:
            issue = ProductionIssue(code="CONTRACT_WARNING", severity="warning", stage_id="prompts", message=warning, shot_id=shot.shot_id, episode_id=shot.series_episode_id)
            state.issues.append(issue)
            prompt_issues.append(issue)

        pack = _latest_pack(session, shot.shot_id)
        if pack:
            state.pack_id = pack.pack_id
            state.pack_ready = pack.readiness != "BLOCKED"
            state.stale_pack = not getattr(pack, "continuity_contract_hash", "") or getattr(pack, "continuity_contract_hash", "") != contract.contract_hash
            if state.stale_pack:
                issue = ProductionIssue(
                    code="STALE_PROMPT_PACK", severity="blocker", stage_id="prompts",
                    message="World/Character/Reference 변경 후 Prompt Pack이 오래되었습니다.",
                    action="08 GENERATE에서 Prompt Pack 다시 만들기",
                    shot_id=shot.shot_id, episode_id=shot.series_episode_id,
                )
                state.issues.append(issue); prompt_issues.append(issue)
            elif pack.readiness == "BLOCKED":
                issue = ProductionIssue(code="PACK_BLOCKED", severity="blocker", stage_id="prompts", message=f"{shot.shot_id} Prompt Pack BLOCKED", action="Generate 경고 해결", shot_id=shot.shot_id)
                state.issues.append(issue); prompt_issues.append(issue)
            else:
                pack_ready_count += 1
        else:
            issue = ProductionIssue(code="NO_PROMPT_PACK", severity="blocker", stage_id="prompts", message=f"{shot.shot_id} Prompt Pack이 없습니다.", action="08 GENERATE에서 생성", shot_id=shot.shot_id)
            state.issues.append(issue); prompt_issues.append(issue)

        take = _accepted_take(session, shot.shot_id)
        if take:
            state.accepted_take_id = take.take_id
            accepted_count += 1
            path = resolve_take_path(take, session.project_dir)
            if not path.is_file():
                issue = ProductionIssue(code="MISSING_ACCEPTED_TAKE", severity="blocker", stage_id="takes", message=f"{shot.shot_id} accepted Take 파일이 없습니다.", action="RESULT/TAKES에서 다시 연결", shot_id=shot.shot_id)
                state.issues.append(issue); take_issues.append(issue)
            report = _latest_qc(session, take.take_id)
            if report:
                state.technical_qc_status = report.status
                technical_by_take[take.take_id] = report.status
                if report.status in {"BLOCKED", "REGENERATE"}:
                    issue = ProductionIssue(code="TECHNICAL_QC_FAIL", severity="blocker", stage_id="qc", message=f"{shot.shot_id} 기술 QC {report.status}", action=report.recommended_action, shot_id=shot.shot_id)
                    state.issues.append(issue); qc_issues.append(issue)
                elif report.status == "REVIEW":
                    issue = ProductionIssue(code="TECHNICAL_QC_REVIEW", severity="warning", stage_id="qc", message=f"{shot.shot_id} 기술 QC REVIEW", action=report.recommended_action, shot_id=shot.shot_id)
                    state.issues.append(issue); qc_issues.append(issue)
                else:
                    qc_ready_count += 1
            else:
                issue = ProductionIssue(code="NO_TECHNICAL_QC", severity="blocker", stage_id="qc", message=f"{shot.shot_id} accepted Take 기술 QC가 없습니다.", action="09 QC에서 검사", shot_id=shot.shot_id)
                state.issues.append(issue); qc_issues.append(issue)

            state.semantic_qc_status = _semantic_status(session, take.take_id)
            if state.semantic_qc_status == "REVIEW":
                issue = ProductionIssue(code="SEMANTIC_QC_REVIEW", severity="warning", stage_id="qc", message=f"{shot.shot_id} 의미/레퍼런스 QC REVIEW", action="시각 연속성 확인", shot_id=shot.shot_id)
                state.issues.append(issue); qc_issues.append(issue)
            elif state.semantic_qc_status == "REGENERATE":
                issue = ProductionIssue(code="SEMANTIC_QC_FAIL", severity="blocker", stage_id="qc", message=f"{shot.shot_id} 의미/레퍼런스 QC 재생성 권고", action="Take 재생성/교체", shot_id=shot.shot_id)
                state.issues.append(issue); qc_issues.append(issue)
            elif state.semantic_qc_status == "MISSING":
                issue = ProductionIssue(code="NO_SEMANTIC_QC", severity="warning", stage_id="qc", message=f"{shot.shot_id} 고급 시각 QC가 없습니다.", action="선택 기능; 필요하면 OpenCLIP 분석", shot_id=shot.shot_id)
                state.issues.append(issue); qc_issues.append(issue)
        else:
            issue = ProductionIssue(code="NO_ACCEPTED_TAKE", severity="blocker", stage_id="takes", message=f"{shot.shot_id} accepted Take가 없습니다.", action="RESULT/TAKES에서 하나 선택", shot_id=shot.shot_id)
            state.issues.append(issue); take_issues.append(issue)

        shot_states.append(state)

    stages.append(_stage("prompts", "08 GENERATE / CONTRACT", prompt_issues, pack_ready_count, len(session.shots)))
    stages.append(_stage("takes", "RESULT / TAKES", take_issues, accepted_count, len(session.shots)))

    # Adjacent visual QC is read-only; unreadable/missing files are already caught elsewhere.
    if accepted_count >= 2:
        try:
            for finding in adjacent_visual_findings(session):
                qc_issues.append(ProductionIssue(
                    code=finding.finding_id,
                    severity="warning" if finding.status == "REVIEW" else "info",
                    stage_id="qc",
                    message=finding.summary_ko,
                ))
        except (OSError, ValueError, ImportError):
            qc_issues.append(ProductionIssue(code="SEQUENCE_VISUAL_QC_SKIPPED", severity="warning", stage_id="qc", message="인접 Shot 시각 연속성 검사를 완료하지 못했습니다.", action="파일/선택 기능 상태 확인"))
    stages.append(_stage("qc", "09 QC / SEQUENCE", qc_issues, qc_ready_count, len(session.shots)))

    # Edit/render.
    edit_issues: list[ProductionIssue] = []
    if session.edit_timeline is None:
        edit_issues.append(ProductionIssue(code="NO_EDIT_TIMELINE", severity="blocker", stage_id="edit", message="자동 편집 Timeline이 없습니다.", action="10 EDIT / RENDER에서 자동 편집 만들기"))
    else:
        try:
            ready = check_readiness(session, session.edit_timeline, session.render_settings)
            for item in ready.issues:
                edit_issues.append(ProductionIssue(
                    code=item.code,
                    severity=item.severity,
                    stage_id="edit",
                    message=item.message,
                    action=item.action,
                    shot_id=item.shot_id,
                ))
        except Exception as exc:
            edit_issues.append(ProductionIssue(code="EDIT_READINESS_ERROR", severity="blocker", stage_id="edit", message=f"편집 준비 검사를 완료할 수 없습니다: {exc}", action="EDIT / RENDER 상태 확인"))
    final_exists = bool(session.final_path and _portable_resolve(session.final_path, session.project_dir).is_file())
    if session.edit_timeline is not None and not final_exists:
        edit_issues.append(ProductionIssue(code="NO_FINAL_RENDER", severity="warning", stage_id="edit", message="최종 렌더 파일이 아직 없습니다.", action="최종 영상 내보내기"))
    stages.append(_stage("edit", "10 EDIT / RENDER", edit_issues, 1 if session.edit_timeline else 0, 1))

    all_issues = [issue for stage in stages for issue in stage.issues]
    blockers = sum(issue.severity == "blocker" for issue in all_issues)
    warnings = sum(issue.severity == "warning" for issue in all_issues)
    status = "BLOCKED" if blockers else "READY_WITH_WARNINGS" if warnings else "READY"

    # Ordered, deduplicated beginner next-actions.
    actions: list[str] = []
    for issue in all_issues:
        if issue.action and issue.action not in actions:
            actions.append(issue.action)
        if len(actions) >= 8:
            break

    return ProductionReadinessReport(
        created_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        stages=stages,
        shots=shot_states,
        blockers=blockers,
        warnings=warnings,
        next_actions=actions,
    )


class GenerationJob(BaseModel):
    job_id: str
    shot_id: str
    pack_id: str
    adapter: GenerationAdapter = "MANUAL"
    status: JobStatus = "PENDING"
    attempts: int = 0
    provider_job_id: str = ""
    output_paths: list[str] = Field(default_factory=list)
    last_error: str = ""
    created_at: str
    updated_at: str


class GenerationQueue:
    """Thread-safe in-memory queue. It never moves/deletes user media."""

    def __init__(self):
        self.jobs: list[GenerationJob] = []
        self._lock = threading.RLock()

    def add(self, shot_id: str, pack_id: str, adapter: GenerationAdapter = "MANUAL", *, allow_duplicate: bool = False) -> GenerationJob:
        with self._lock:
            if not allow_duplicate:
                existing = next((
                    job for job in self.jobs
                    if job.shot_id == shot_id and job.pack_id == pack_id and job.adapter == adapter
                    and job.status in {"PENDING", "RUNNING"}
                ), None)
                if existing:
                    return existing
            stamp = datetime.now(timezone.utc).isoformat()
            job = GenerationJob(
                job_id=f"JOB-{uuid4().hex[:12].upper()}",
                shot_id=shot_id,
                pack_id=pack_id,
                adapter=adapter,
                created_at=stamp,
                updated_at=stamp,
            )
            self.jobs.append(job)
            return job

    def next_pending(self, adapter: GenerationAdapter | None = None) -> GenerationJob | None:
        with self._lock:
            return next((job for job in self.jobs if job.status == "PENDING" and (adapter is None or job.adapter == adapter)), None)

    def start(self, job_id: str, provider_job_id: str = "") -> GenerationJob:
        with self._lock:
            job = self._job(job_id)
            if job.status not in {"PENDING", "FAILED"}:
                raise ValueError(f"Job is not startable from {job.status}: {job_id}")
            job.status = "RUNNING"
            job.attempts += 1
            job.provider_job_id = provider_job_id
            job.last_error = ""
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job

    def complete(self, job_id: str, output_paths: list[str] | None = None) -> GenerationJob:
        with self._lock:
            job = self._job(job_id)
            if job.status != "RUNNING":
                raise ValueError(f"Job is not RUNNING: {job_id}")
            job.status = "DONE"
            job.output_paths = list(output_paths or [])
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job

    def fail(self, job_id: str, error: str) -> GenerationJob:
        with self._lock:
            job = self._job(job_id)
            if job.status not in {"RUNNING", "PENDING"}:
                raise ValueError(f"Job cannot fail from {job.status}: {job_id}")
            job.status = "FAILED"
            job.last_error = str(error)
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job

    def requeue(self, job_id: str) -> GenerationJob:
        with self._lock:
            job = self._job(job_id)
            if job.status != "FAILED":
                raise ValueError("Only FAILED jobs can be requeued.")
            job.status = "PENDING"
            job.last_error = ""
            job.provider_job_id = ""
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job

    def cancel(self, job_id: str) -> GenerationJob:
        with self._lock:
            job = self._job(job_id)
            if job.status == "DONE":
                raise ValueError("Completed jobs are immutable.")
            job.status = "CANCELLED"
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {
                status: sum(job.status == status for job in self.jobs)
                for status in ("PENDING", "RUNNING", "DONE", "FAILED", "CANCELLED")
            }

    def _job(self, job_id: str) -> GenerationJob:
        job = next((item for item in self.jobs if item.job_id == job_id), None)
        if not job:
            raise ValueError(f"Unknown job_id: {job_id}")
        return job


def build_generation_queue(session: LyricsWorldSession, queue: GenerationQueue, adapter: GenerationAdapter = "MANUAL") -> list[GenerationJob]:
    """Queue latest non-blocked, non-stale packs for shots without an accepted Take."""
    report = build_production_readiness(session)
    created: list[GenerationJob] = []
    for state in report.shots:
        if state.accepted_take_id or not state.pack_id or not state.pack_ready or state.stale_pack:
            continue
        created.append(queue.add(state.shot_id, state.pack_id, adapter))
    return created


class ComfyUIStatus(BaseModel):
    state: Literal["AVAILABLE", "NOT_RUNNING", "INVALID_ENDPOINT", "ERROR"]
    endpoint: str
    detail: str = ""


def _is_local_endpoint(endpoint: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(endpoint)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").casefold() in {"127.0.0.1", "localhost", "::1"}


class ComfyUIBridge:
    """Minimal optional bridge to a user-managed local ComfyUI server.

    It never installs ComfyUI, downloads checkpoints, changes workflows, or calls cloud
    providers on its own. Remote endpoints are denied unless allow_remote=True.
    """

    def __init__(self, endpoint: str = "http://127.0.0.1:8188", timeout_sec: float = 4.0, *, allow_remote: bool = False):
        self.endpoint = endpoint.rstrip("/")
        self.timeout_sec = max(0.5, float(timeout_sec))
        self.allow_remote = allow_remote

    def _validate(self) -> None:
        parsed = urllib.parse.urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("ComfyUI endpoint 형식이 올바르지 않습니다.")
        if not self.allow_remote and not _is_local_endpoint(self.endpoint):
            raise ValueError("안전을 위해 기본 설정에서는 localhost/127.0.0.1 ComfyUI만 허용합니다.")

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        self._validate()
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint + path,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
            method="POST" if body is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def status(self) -> ComfyUIStatus:
        try:
            payload = self._request("/system_stats")
            detail = "ComfyUI local server responding"
            if isinstance(payload, dict) and payload.get("system"):
                detail = "ComfyUI local server + system stats available"
            return ComfyUIStatus(state="AVAILABLE", endpoint=self.endpoint, detail=detail)
        except ValueError as exc:
            return ComfyUIStatus(state="INVALID_ENDPOINT", endpoint=self.endpoint, detail=str(exc))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            return ComfyUIStatus(state="NOT_RUNNING", endpoint=self.endpoint, detail=str(exc))
        except Exception as exc:
            return ComfyUIStatus(state="ERROR", endpoint=self.endpoint, detail=str(exc))

    def queue_workflow(self, workflow_api_json: dict[str, Any], *, client_id: str | None = None) -> str:
        payload = {"prompt": workflow_api_json, "client_id": client_id or f"mvstudio-{uuid4().hex}"}
        result = self._request("/prompt", payload)
        prompt_id = str(result.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI가 prompt_id를 반환하지 않았습니다: {result}")
        return prompt_id

    def history(self, prompt_id: str) -> dict[str, Any]:
        result = self._request(f"/history/{urllib.parse.quote(prompt_id)}")
        return result if isinstance(result, dict) else {}

    def queue_state(self) -> dict[str, Any]:
        result = self._request("/queue")
        return result if isinstance(result, dict) else {}

    def interrupt(self) -> None:
        self._request("/interrupt", {})


PLACEHOLDERS = {
    "{{MV_MAIN_PROMPT}}": "main_prompt",
    "{{MV_MOTION_PROMPT}}": "motion_prompt",
    "{{MV_CAMERA_PROMPT}}": "camera_prompt",
    "{{MV_NEGATIVE_PROMPT}}": "negative_prompt",
    "{{MV_SHOT_ID}}": "shot_id",
    "{{MV_DURATION}}": "duration_sec",
    "{{MV_ASPECT_RATIO}}": "aspect_ratio",
}


def materialize_comfyui_workflow(template: dict[str, Any], pack, *, output_prefix: str | None = None) -> dict[str, Any]:
    """Replace explicit placeholders in an exported ComfyUI API-format workflow."""
    replacements = {
        token: str(getattr(pack, attr, ""))
        for token, attr in PLACEHOLDERS.items()
    }
    replacements["{{MV_OUTPUT_PREFIX}}"] = output_prefix or f"mvstudio/{pack.shot_id}/{pack.pack_id}"

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            result = value
            for token, replacement in replacements.items():
                result = result.replace(token, replacement)
            return result
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(json.loads(json.dumps(template)))


def extract_comfyui_output_files(history_payload: dict[str, Any], prompt_id: str) -> list[str]:
    """Return filenames reported by standard SaveImage/SaveAnimatedWEBP/video-like outputs."""
    node_history = history_payload.get(prompt_id, history_payload)
    outputs = node_history.get("outputs", {}) if isinstance(node_history, dict) else {}
    result: list[str] = []
    for output in outputs.values() if isinstance(outputs, dict) else []:
        if not isinstance(output, dict):
            continue
        for key in ("images", "gifs", "videos"):
            for item in output.get(key, []) or []:
                if isinstance(item, dict) and item.get("filename"):
                    subfolder = item.get("subfolder") or ""
                    filename = str(Path(subfolder) / item["filename"]) if subfolder else str(item["filename"])
                    result.append(filename)
    return list(dict.fromkeys(result))


class FinalRenderFinding(BaseModel):
    code: str
    severity: Literal["blocker", "warning", "info"]
    message: str
    value: float | int | str | None = None


class FinalRenderVerification(BaseModel):
    status: Literal["PASS", "PASS_WITH_WARNINGS", "FAIL"]
    path: str
    duration_sec: float = 0.0
    expected_duration_sec: float = 0.0
    black_frame_ratio: float | None = None
    freeze_ratio: float | None = None
    scene_cut_count: int | None = None
    expected_boundary_count: int = 0
    findings: list[FinalRenderFinding] = Field(default_factory=list)


def _sample_render_health(path: Path, max_samples: int = 120) -> tuple[float | None, float | None]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None, None

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        return None, None
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
    stride = max(1, frame_count // max(2, max_samples))
    black = 0
    frozen = 0
    sampled = 0
    previous = None
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % stride == 0:
            small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sampled += 1
            if float(np.mean(gray)) < 8.0:
                black += 1
            if previous is not None and float(np.mean(cv2.absdiff(previous, gray))) < 0.45:
                frozen += 1
            previous = gray
        index += 1
    capture.release()
    if not sampled:
        return None, None
    return black / sampled, frozen / max(1, sampled - 1)


def _scene_cut_count(path: Path) -> int | None:
    try:
        from scenedetect import ContentDetector, detect  # type: ignore
    except ImportError:
        return None
    try:
        scenes = detect(str(path), ContentDetector(threshold=27.0))
        return max(0, len(scenes) - 1)
    except Exception:
        return None


def verify_final_render(session: LyricsWorldSession, path: str | Path | None = None) -> FinalRenderVerification:
    candidate = path or session.final_path
    if not candidate:
        return FinalRenderVerification(
            status="FAIL", path="", findings=[
                FinalRenderFinding(code="NO_FINAL_PATH", severity="blocker", message="최종 렌더 경로가 없습니다.")
            ],
        )
    target = _portable_resolve(candidate, session.project_dir)
    findings: list[FinalRenderFinding] = []
    if not target.is_file():
        return FinalRenderVerification(
            status="FAIL", path=str(target), findings=[
                FinalRenderFinding(code="MISSING_FINAL", severity="blocker", message="최종 렌더 파일을 찾을 수 없습니다.")
            ],
        )

    try:
        media = probe_media(target)
    except Exception as exc:
        return FinalRenderVerification(
            status="FAIL", path=str(target), findings=[
                FinalRenderFinding(code="UNREADABLE_FINAL", severity="blocker", message=f"최종 렌더를 읽을 수 없습니다: {exc}")
            ],
        )

    expected = (
        session.audio_map.duration_sec if session.audio_map
        else session.edit_timeline.duration_sec if session.edit_timeline
        else session.duration_sec or 0.0
    )
    tolerance = max(0.25, 1.5 / max(1.0, session.render_settings.fps))
    if expected and abs(media.duration_sec - expected) > tolerance:
        findings.append(FinalRenderFinding(
            code="DURATION_MISMATCH", severity="blocker",
            message=f"최종 영상 길이({media.duration_sec:.3f}s)가 음악/타임라인({expected:.3f}s)과 다릅니다.",
            value=abs(media.duration_sec - expected),
        ))
    if not media.has_audio:
        findings.append(FinalRenderFinding(code="NO_AUDIO", severity="blocker", message="최종 영상에 오디오 트랙이 없습니다."))
    if media.width != session.render_settings.width or media.height != session.render_settings.height:
        findings.append(FinalRenderFinding(
            code="OUTPUT_SIZE_MISMATCH", severity="blocker",
            message=f"최종 해상도가 설정과 다릅니다: {media.width}x{media.height}",
        ))
    if media.fps and abs(media.fps - session.render_settings.fps) > 0.6:
        findings.append(FinalRenderFinding(code="OUTPUT_FPS_MISMATCH", severity="warning", message=f"최종 FPS가 설정과 다를 수 있습니다: {media.fps:.2f}", value=media.fps))

    black_ratio, freeze_ratio = _sample_render_health(target)
    if black_ratio is not None and black_ratio > 0.025:
        findings.append(FinalRenderFinding(code="BLACK_FRAME_RATIO", severity="warning", message="최종 영상에 검은 프레임 비율이 높습니다.", value=round(black_ratio, 4)))
    # Long hold_last can be intentional, so freeze is a warning rather than blocker.
    if freeze_ratio is not None and freeze_ratio > 0.45:
        findings.append(FinalRenderFinding(code="FREEZE_RATIO", severity="warning", message="최종 영상에 정지 프레임 구간이 많습니다.", value=round(freeze_ratio, 4)))

    cut_count = _scene_cut_count(target)
    expected_boundaries = 0
    if session.edit_timeline:
        expected_boundaries = max(0, len(session.edit_timeline.clips) + len(session.edit_timeline.gaps) - 1)
        if cut_count is not None and expected_boundaries >= 2 and cut_count > expected_boundaries * 4 + 4:
            findings.append(FinalRenderFinding(
                code="EXCESS_SCENE_CUTS", severity="warning",
                message="최종 렌더에서 예상보다 훨씬 많은 장면 전환이 감지됩니다.",
                value=cut_count,
            ))

    status = "FAIL" if any(item.severity == "blocker" for item in findings) else "PASS_WITH_WARNINGS" if any(item.severity == "warning" for item in findings) else "PASS"
    return FinalRenderVerification(
        status=status,
        path=str(target),
        duration_sec=media.duration_sec,
        expected_duration_sec=expected,
        black_frame_ratio=round(black_ratio, 4) if black_ratio is not None else None,
        freeze_ratio=round(freeze_ratio, 4) if freeze_ratio is not None else None,
        scene_cut_count=cut_count,
        expected_boundary_count=expected_boundaries,
        findings=findings,
    )


def production_state_fingerprint(session: LyricsWorldSession) -> str:
    """Stable fingerprint for simulation/staleness checks without media bytes."""
    payload = {
        "music": session.music_path,
        "audio_map": session.audio_map.model_dump(mode="json") if session.audio_map else None,
        "world_bible": session.world_bible.model_dump(mode="json") if session.world_bible else None,
        "series_bible": session.series_bible.model_dump(mode="json") if session.series_bible else None,
        "series_entities": [entity.model_dump(mode="json") for entity in session.series_entities],
        "series_assets": [asset.model_dump(mode="json") for asset in session.series_assets],
        "beats": [beat.model_dump(mode="json") for beat in session.story_beats],
        "shots": [shot.model_dump(mode="json") for shot in session.shots],
        "packs": [
            {
                "pack_id": pack.pack_id,
                "shot_id": pack.shot_id,
                "contract_hash": getattr(pack, "continuity_contract_hash", ""),
                "readiness": pack.readiness,
            }
            for pack in session.generation_packs
        ],
        "takes": [
            {
                "take_id": take.take_id,
                "shot_id": take.shot_id,
                "pack_id": take.pack_id,
                "status": take.status,
                "output_path": take.output_path,
            }
            for take in session.generation_takes
        ],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
