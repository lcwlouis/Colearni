"""In-memory tutor state store — keyed by chat session ID.

v1 uses a simple dict. v2 can persist to DB or Redis.
"""
from __future__ import annotations
import threading
from core.schemas.tutor_state import TutorState


_lock = threading.Lock()
_store: dict[int, TutorState] = {}


def get_tutor_state(session_id: int) -> TutorState:
    """Get or create tutor state for a session."""
    with _lock:
        if session_id not in _store:
            _store[session_id] = TutorState()
        return _store[session_id].model_copy(deep=True)


def save_tutor_state(session_id: int, state: TutorState) -> None:
    """Persist tutor state for a session."""
    with _lock:
        _store[session_id] = state.model_copy(deep=True)


def clear_tutor_state(session_id: int) -> None:
    """Remove tutor state for a session (e.g. on session delete)."""
    with _lock:
        _store.pop(session_id, None)


def is_tutor_active(session_id: int) -> bool:
    """Check if interactive tutor mode is active for this session."""
    with _lock:
        state = _store.get(session_id)
        return state is not None and state.active
