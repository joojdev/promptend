from pathlib import Path

import pytest


def _settings(**kwargs):
    from src.config.settings import Settings

    return Settings(
        _env_file=None, llm_provider="anthropic", llm_api_key="k", llm_model="m", **kwargs
    )


@pytest.fixture()
def presets_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("PERSONALITY", raising=False)
    monkeypatch.delenv("PERSONALITY_PATH", raising=False)
    directory = tmp_path / "personalities"
    directory.mkdir()
    (directory / "default.md").write_text("Default persona.")
    (directory / "shop.md").write_text("Shop persona.")
    return directory


# US1


def test_unset_personality_resolves_default(presets_dir):
    from src.config.personality import PersonalitySource, resolve_personality

    source = resolve_personality(_settings(), presets_dir=presets_dir)
    assert source == PersonalitySource(path=presets_dir / "default.md", preset="default")


@pytest.mark.parametrize("name", ["shop", "Shop", " shop ", "SHOP\n"])
def test_named_preset_resolves_normalized(presets_dir, name):
    from src.config.personality import PersonalitySource, resolve_personality

    source = resolve_personality(_settings(personality=name), presets_dir=presets_dir)
    assert source == PersonalitySource(path=presets_dir / "shop.md", preset="shop")


def test_available_presets_lists_md_stems_only(presets_dir):
    from src.config.personality import available_presets

    (presets_dir / ".gitkeep").write_text("")
    (presets_dir / "notes.txt").write_text("x")
    (presets_dir / "nested.md").mkdir()
    (presets_dir / "sub").mkdir()
    (presets_dir / "sub" / "inner.md").write_text("x")
    assert available_presets(presets_dir) == ["default", "shop"]


def test_available_presets_missing_dir_is_empty(tmp_path):
    from src.config.personality import available_presets

    assert available_presets(tmp_path / "nope") == []


# US2


def test_custom_path_wins_over_preset(presets_dir, tmp_path):
    from src.config.personality import PersonalitySource, resolve_personality

    custom = tmp_path / "custom.md"
    custom.write_text("Custom persona.")
    source = resolve_personality(
        _settings(personality="teapot", personality_path=str(custom)), presets_dir=presets_dir
    )
    assert source == PersonalitySource(path=Path(custom), preset=None)


def test_blank_custom_path_is_unset(presets_dir):
    from src.config.personality import PersonalitySource, resolve_personality

    source = resolve_personality(_settings(personality_path="   "), presets_dir=presets_dir)
    assert source == PersonalitySource(path=presets_dir / "default.md", preset="default")


def test_missing_custom_path_fails_in_load_harness(presets_dir, tmp_path, monkeypatch, capsys):
    from src.agent.harness import load_harness
    from src.config.personality import resolve_personality

    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    missing = tmp_path / "missing.md"
    source = resolve_personality(_settings(personality_path=str(missing)), presets_dir=presets_dir)
    assert source.path == missing

    with pytest.raises(SystemExit):
        load_harness(str(source.path))
    assert "personality file not found" in capsys.readouterr().err


# US3


def test_unknown_preset_exits_listing_presets(presets_dir, capsys):
    from src.config.personality import resolve_personality

    with pytest.raises(SystemExit) as exc:
        resolve_personality(_settings(personality="nope"), presets_dir=presets_dir)
    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert "unknown personality preset 'nope'" in err
    assert "Available presets: default, shop" in err


@pytest.mark.parametrize("name", ["../secrets", "a/b", "a\\b", ".."])
def test_unsafe_preset_name_exits(presets_dir, capsys, name):
    from src.config.personality import resolve_personality

    (presets_dir.parent / "secrets.md").write_text("SECRET")
    with pytest.raises(SystemExit) as exc:
        resolve_personality(_settings(personality=name), presets_dir=presets_dir)
    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert "unknown personality preset" in err
    assert "Available presets: default, shop" in err


@pytest.mark.parametrize("make", [True, False])
def test_no_presets_exits(tmp_path, capsys, monkeypatch, make):
    from src.config.personality import resolve_personality

    monkeypatch.delenv("PERSONALITY_PATH", raising=False)
    directory = tmp_path / "empty"
    if make:
        directory.mkdir()
        (directory / ".gitkeep").write_text("")
    with pytest.raises(SystemExit) as exc:
        resolve_personality(_settings(), presets_dir=directory)
    assert exc.value.code == 1
    assert f"no personality presets found in {directory.as_posix()}" in capsys.readouterr().err
