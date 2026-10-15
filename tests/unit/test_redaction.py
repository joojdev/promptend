import pytest

from src.api.guards import redact_headers

NAMES = frozenset({"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"})
FRAGMENTS = ("token", "secret", "key")


def test_exact_names_redacted():
    headers = {name: "v" for name in NAMES}
    out = redact_headers(headers, NAMES, FRAGMENTS)
    assert set(out) == NAMES - {"authorization", "x-api-key"}
    assert all(v == "[REDACTED]" for v in out.values())


def test_fragment_matches_case_insensitive():
    headers = {"X-Auth-Token": "a", "X-CLIENT-SECRET": "b", "My-Key-Id": "c"}
    out = redact_headers(headers, NAMES, FRAGMENTS)
    assert out == {k: "[REDACTED]" for k in headers}


def test_ordinary_headers_unchanged():
    headers = {"content-type": "application/json", "user-agent": "ua", "cookie": "x"}
    out = redact_headers(headers, NAMES, FRAGMENTS)
    assert out["content-type"] == "application/json"
    assert out["user-agent"] == "ua"
    assert out["cookie"] == "[REDACTED]"


@pytest.mark.parametrize("name", ["authorization", "Authorization", "X-API-Key", "x-api-key"])
def test_credential_headers_dropped(name):
    out = redact_headers({name: "secret", "accept": "*/*"}, NAMES, FRAGMENTS)
    assert out == {"accept": "*/*"}


def test_former_access_key_header_is_masked_like_any_key():
    out = redact_headers({"x-legacy-key": "k"}, NAMES, FRAGMENTS)
    assert out == {"x-legacy-key": "[REDACTED]"}


def test_custom_rule_overrides_defaults():
    out = redact_headers(
        {"authorization": "a", "x-mine": "b", "x-passcode": "c"},
        frozenset({"x-mine"}),
        ("passcode",),
    )
    assert out == {"x-mine": "[REDACTED]", "x-passcode": "[REDACTED]"}
