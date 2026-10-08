from __future__ import annotations

from pydantic import BaseModel, Field


EXPECTED_NAV = [
    "01  MUSIC",
    "02  LYRICS & MEANING",
    "03  WORLD LAB",
    "04  WORLD BIBLE",
    "05  REFERENCE VAULT",
    "06  STORY ROOM",
    "07  SHOT BOARD",
    "08  GENERATE",
    "09  QC",
    "10  EDIT / RENDER",
]


class UIContractFinding(BaseModel):
    code: str
    message: str


class UIContractReport(BaseModel):
    passed: bool
    findings: list[UIContractFinding] = Field(default_factory=list)
    nav_count: int = 0
    page_count: int = 0
    size: tuple[int, int] = (0, 0)


def validate_main_window_contract(window) -> UIContractReport:
    findings: list[UIContractFinding] = []
    nav_text = [button.text() for button in getattr(window, "nav_buttons", [])]
    if nav_text != EXPECTED_NAV:
        findings.append(UIContractFinding(code="NAV_ORDER", message=f"Navigation mismatch: {nav_text}"))
    pages = getattr(window, "pages", None)
    page_count = pages.count() if pages is not None else -1
    if page_count != len(EXPECTED_NAV):
        findings.append(UIContractFinding(code="PAGE_COUNT", message=f"Expected {len(EXPECTED_NAV)} pages, got {page_count}"))

    required = [
        "story_room_page", "shot_board_page", "manual_generation_page", "result_takes_page",
        "technical_qc_page", "editor_render_page", "series_button", "production_control_button",
    ]
    for name in required:
        if not hasattr(window, name):
            findings.append(UIContractFinding(code="MISSING_WIDGET", message=f"Missing required UI attribute: {name}"))

    for name in (
        "story_room_page", "shot_board_page", "manual_generation_page",
        "result_takes_page", "technical_qc_page", "editor_render_page",
    ):
        widget = getattr(window, name, None)
        if widget is not None and not callable(getattr(widget, "refresh", None)):
            findings.append(UIContractFinding(code="MISSING_REFRESH", message=f"{name} has no refresh()"))

    if window.minimumWidth() > 1100 or window.minimumHeight() > 720:
        findings.append(UIContractFinding(
            code="MIN_SIZE",
            message=f"Window minimum {window.minimumWidth()}x{window.minimumHeight()} exceeds 1100x720 contract.",
        ))

    return UIContractReport(
        passed=not findings,
        findings=findings,
        nav_count=len(nav_text),
        page_count=page_count,
        size=(window.width(), window.height()),
    )


def validate_production_dialog_contract(dialog) -> UIContractReport:
    findings: list[UIContractFinding] = []
    if dialog.minimumWidth() > 1100 or dialog.minimumHeight() > 720:
        findings.append(UIContractFinding(code="PRODUCTION_MIN_SIZE", message="Production Control exceeds 1100x720 minimum contract."))
    expected_tabs = ["전체 준비 상태", "생성 대기열", "최종 영상 검증"]
    tab_names = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    if tab_names != expected_tabs:
        findings.append(UIContractFinding(code="PRODUCTION_TABS", message=f"Production tabs mismatch: {tab_names}"))
    for name in (
        "readiness_status", "stage_list", "issue_detail", "next_actions",
        "queue_list", "queue_detail", "final_result",
    ):
        if not hasattr(dialog, name):
            findings.append(UIContractFinding(code="PRODUCTION_WIDGET", message=f"Missing Production Control widget: {name}"))
    return UIContractReport(
        passed=not findings,
        findings=findings,
        nav_count=0,
        page_count=dialog.tabs.count(),
        size=(dialog.width(), dialog.height()),
    )
