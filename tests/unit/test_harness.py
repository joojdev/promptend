# T012
def test_system_prompt_contains_both_sections(tmp_path, monkeypatch):
    personality_content = "I am a sarcastic butler."
    personality_file = tmp_path / "personality.md"
    personality_file.write_text(personality_content)

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality_file))

    from src.agent.harness import build_system_prompt

    prompt = build_system_prompt(str(personality_file))

    assert personality_content in prompt
    assert "respond" in prompt.lower()


# T013
def test_empty_personality_yields_only_programmatic_block(tmp_path, monkeypatch):
    personality_file = tmp_path / "personality.md"
    personality_file.write_text("")

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality_file))

    from src.agent.harness import build_system_prompt

    prompt = build_system_prompt(str(personality_file))

    assert prompt.strip() != ""
    assert "respond" in prompt.lower()
    assert len(prompt.strip().splitlines()) > 0
