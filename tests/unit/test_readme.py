import re
from pathlib import Path

import pytest

from src.config.personality import available_presets
from src.config.settings import Settings

ROOT = Path(__file__).resolve().parents[2]

SECTIONS = [
    "What is this?",
    "How it works",
    "Quickstart",
    "Configuration",
    "Personalities",
    "Why you should never use this in production",
    "How it was built",
    "Contributing",
    "License",
]


@pytest.fixture(scope="module")
def readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"missing section {title!r}"
    return match.group(1)


def _table_names(readme: str) -> set[str]:
    rows = [line for line in _section(readme, "Configuration").splitlines() if line.startswith("|")]
    names = set()
    for row in rows:
        first = row.strip("|").split("|")[0]
        names.update(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", first))
    return names


def test_sections_in_order(readme):
    headings = re.findall(r"^## (.+)$", readme, re.M)
    assert headings == SECTIONS


def test_every_setting_documented(readme):
    names = _table_names(readme)
    for field in Settings.model_fields:
        assert field.upper() in names, field


def test_no_unknown_setting_documented(readme):
    known = {field.upper() for field in Settings.model_fields}
    assert _table_names(readme) <= known


def test_every_preset_mentioned(readme):
    section = _section(readme, "Personalities")
    for preset in available_presets(ROOT / "config" / "personalities"):
        assert f"`{preset}`" in section, preset


def test_no_removed_access_key(readme):
    assert "DOPAMINE_ACCESS_KEY" not in readme
    assert "X-Legacy-Key" not in readme
