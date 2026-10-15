from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_token_store_dir_ignored():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert "data/" in lines


def test_gitattributes_marks_vendored_and_docs():
    lines = (ROOT / ".gitattributes").read_text().splitlines()
    for line in (
        ".specify/** linguist-vendored",
        ".claude/** linguist-vendored",
        "specs/** linguist-documentation",
    ):
        assert line in lines


def test_mit_license():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 João Vitor Piovezan" in text


def test_license_metadata():
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]


def test_spec_kit_dirs_kept():
    assert (ROOT / ".specify").is_dir()
    assert (ROOT / "specs").is_dir()
