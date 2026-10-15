from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_token_store_dir_ignored():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    assert "data/" in lines
