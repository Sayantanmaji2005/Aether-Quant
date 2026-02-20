from aetherquant.rate_limit import InMemoryRateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter(limit_per_minute=2)
    assert limiter.allow("k", now=100.0)[0] is True
    assert limiter.allow("k", now=101.0)[0] is True
    allowed, retry_after = limiter.allow("k", now=102.0)
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_resets_after_window() -> None:
    limiter = InMemoryRateLimiter(limit_per_minute=1)
    assert limiter.allow("k", now=100.0)[0] is True
    assert limiter.allow("k", now=161.0)[0] is True
