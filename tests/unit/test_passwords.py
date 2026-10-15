import pytest

from src.auth.passwords import AdminVerifier, InvalidAdminHash, hash_password, validate_hash
from tests.conftest import fast_hash


def test_hash_password_is_argon2id():
    h = hash_password("pw")
    assert h.startswith("$argon2id$")
    validate_hash(h)


@pytest.mark.parametrize(
    "value", ["not-a-hash", "$2b$12$abcdefghijklmnopqrstuuS1D6kV9N1aGv2h2Bq8V9Vq0v6cH5M8e"]
)
def test_invalid_hash_rejected_without_echo(value):
    with pytest.raises(InvalidAdminHash) as exc:
        validate_hash(value)
    assert value not in str(exc.value)


@pytest.fixture(scope="module")
def verifier():
    return AdminVerifier("admin", fast_hash("pw"))


def test_correct_credentials(verifier):
    assert verifier.verify("admin", "pw") is True


@pytest.mark.parametrize(
    ("username", "password"), [("admin", "wrong"), ("other", "pw"), ("Admin", "pw"), ("", "")]
)
def test_wrong_credentials(verifier, username, password):
    assert verifier.verify(username, password) is False


def test_wrong_username_still_verifies_against_dummy():
    from argon2 import PasswordHasher

    class SpyHasher(PasswordHasher):
        __slots__ = ("calls",)

        def verify(self, h, password):
            self.calls.append(h)
            return True

    hasher = SpyHasher(time_cost=1, memory_cost=8, parallelism=1)
    hasher.calls = []
    real = fast_hash("pw")
    verifier = AdminVerifier("admin", real, hasher=hasher)
    assert verifier.verify("intruder", "pw") is False
    assert hasher.calls == [verifier._dummy_hash]
    assert real not in hasher.calls
