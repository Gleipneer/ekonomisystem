from __future__ import annotations

from sqlalchemy.orm import Session


def maybe_handle_assistant_prompt(db: Session, household_id: int, prompt: str) -> tuple[bool, str, str]:
    """Return whether prompt was handled by import interceptor.

    Current baseline is conservative and only routes normal assistant prompts
    onward to the assistant engine.
    """

    _ = (db, household_id, prompt)
    return False, "", "import-interceptor-v1"
