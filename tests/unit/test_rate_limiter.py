from src.api import guards
from src.api.guards import RateLimiter


def test_allows_n_then_rejects(monkeypatch):
    monkeypatch.setattr(guards.time, "monotonic", lambda: 100.0)
    rl = RateLimiter(3)
    assert [rl.check("a") for _ in range(4)] == [True, True, True, False]


def test_hosts_independent(monkeypatch):
    monkeypatch.setattr(guards.time, "monotonic", lambda: 100.0)
    rl = RateLimiter(1)
    assert rl.check("a")
    assert not rl.check("a")
    assert rl.check("b")


def test_window_expiry_allows_again(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(guards.time, "monotonic", lambda: now[0])
    rl = RateLimiter(1)
    assert rl.check("a")
    assert not rl.check("a")
    now[0] += 61
    assert rl.check("a")


def test_idle_hosts_pruned(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(guards.time, "monotonic", lambda: now[0])
    rl = RateLimiter(5)
    for i in range(500):
        rl.check(f"host{i}")
    now[0] += 120
    for i in range(500):
        rl.check("busy")
    assert len(rl._hits) < 500
