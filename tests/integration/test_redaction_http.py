from fastapi.testclient import TestClient

from tests.conftest import CountingFakeLLM


def test_secret_headers_never_reach_llm(monkeypatch, tmp_path):
    personality = tmp_path / "personality.md"
    personality.write_text("Test persona.")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("PERSONALITY_PATH", str(personality))

    llm = CountingFakeLLM(responses=["pong"], prompts=[])

    from src.api.app import create_app

    with TestClient(create_app(llm=llm)) as client:
        response = client.post(
            "/x",
            content="hi",
            headers={
                "Authorization": "Bearer abc123",
                "Cookie": "sid=zzz",
                "X-Custom-Token": "tok",
                "User-Agent": "ua-test",
            },
        )
    assert response.status_code == 200
    prompt = "\n".join(llm.prompts)
    assert prompt.count("[REDACTED]") >= 3
    for secret in ("abc123", "sid=zzz", "'tok'"):
        assert secret not in prompt
    assert "ua-test" in prompt
