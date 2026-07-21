from pathlib import Path
from typing import Any

_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")


def load_base_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_system_prompt(session: dict[str, Any] | None = None) -> str:
    prompt = load_base_system_prompt()
    if not session:
        return prompt

    lines = [
        "",
        "## Current session",
        "",
    ]

    field_labels = [
        ("email", "User email"),
        ("sub", "User sub"),
        ("role", "Role"),
        ("project", "Project"),
        ("environment", "Environment"),
        ("repository", "Repository"),
        ("issue_number", "Issue"),
        ("allowed_tools", "Allowed tools"),
    ]
    for key, label in field_labels:
        value = session.get(key)
        if value is None or value == "":
            continue
        if key == "issue_number":
            value = f"#{value}"
        if key == "allowed_tools" and isinstance(value, list):
            value = ", ".join(value)
        lines.append(f"- {label}: {value}")

    if len(lines) <= 3:
        return prompt

    return f"{prompt}\n" + "\n".join(lines)
