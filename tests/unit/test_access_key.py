from src.api import guards
from src.api.guards import check_access_key


def test_disabled_when_expected_empty():
    assert check_access_key(None, "")
    assert check_access_key("anything", "")


def test_correct_key_passes():
    assert check_access_key("s3cret", "s3cret")


def test_missing_and_wrong_fail():
    assert not check_access_key(None, "s3cret")
    assert not check_access_key("wrong", "s3cret")
    assert not check_access_key("s3cret-longer", "s3cret")


def test_uses_compare_digest(monkeypatch):
    calls = []
    real = guards.hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(guards.hmac, "compare_digest", spy)
    check_access_key("x", "y")
    assert calls
