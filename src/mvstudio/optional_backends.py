from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Literal


BackendState = Literal["AVAILABLE", "NOT_INSTALLED", "LOAD_FAILED"]
_RUNTIME_FAILURES: dict[str, str] = {}


@dataclass(frozen=True)
class BackendAvailability:
    backend_id: str
    state: BackendState
    detail: str = ""


def module_availability(backend_id: str, module_name: str) -> BackendAvailability:
    if backend_id in _RUNTIME_FAILURES:
        return BackendAvailability(backend_id, "LOAD_FAILED", _RUNTIME_FAILURES[backend_id])
    try:
        found = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError) as exc:
        return BackendAvailability(backend_id, "LOAD_FAILED", str(exc))
    return BackendAvailability(backend_id, "AVAILABLE" if found else "NOT_INSTALLED")


def mark_backend_load_failed(backend_id: str, detail: str) -> None:
    _RUNTIME_FAILURES[backend_id] = detail


def clear_backend_load_failure(backend_id: str) -> None:
    _RUNTIME_FAILURES.pop(backend_id, None)


def openclip_availability() -> BackendAvailability:
    return module_availability("OPENCLIP", "open_clip")


def beat_this_availability() -> BackendAvailability:
    return module_availability("BEAT_THIS", "beat_this")


def functional_structure_availability() -> BackendAvailability:
    # Adapter target is intentionally isolated. Presence never triggers model loading/download.
    return module_availability("FUNCTIONAL_STRUCTURE", "allin1")
