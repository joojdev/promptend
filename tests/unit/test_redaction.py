from src.api.guards import redact_headers

NAMES = frozenset({"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"})
FRAGMENTS = ("token", "secret", "key")


def test_exact_names_redacted():
    headers = {name: "v" for name in NAMES}
    out = redact_headers(headers, NAMES, FRAGMENTS)
    assert set(out) == NAMES
    assert all(v == "[REDACTED]" for v in out.values())


def test_fragment_matches_case_insensitive():
    headers = {"X-Auth-Token": "a", "X-CLIENT-SECRET": "b", "My-Key-Id": "c"}
    out = redact_headers(headers, NAMES, FRAGMENTS)
    assert out == {k: "[REDACTED]" for k in headers}


def test_ordinary_headers_unchanged_and_names_kept():
    headers = {"content-type": "application/json", "user-agent": "ua", "authorization": "x"}
    out = redact_headers(headers, NAMES, FRAGMENTS)
    assert out["content-type"] == "application/json"
    assert out["user-agent"] == "ua"
    assert "authorization" in out


def test_access_key_header_omitted():
    out = redact_headers({"x-dopamine-key": "k", "accept": "*/*"}, NAMES, FRAGMENTS)
    assert "x-dopamine-key" not in out
    assert out == {"accept": "*/*"}


def test_custom_rule_overrides_defaults():
    out = redact_headers(
        {"authorization": "a", "x-mine": "b", "x-passcode": "c"},
        frozenset({"x-mine"}),
        ("passcode",),
    )
    assert out == {"authorization": "a", "x-mine": "[REDACTED]", "x-passcode": "[REDACTED]"}
