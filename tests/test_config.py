from aetherquant.config import Settings


def test_settings_defaults_are_valid() -> None:
    settings = Settings()
    assert settings.initial_cash > 0
    assert settings.commission_bps >= 0
    assert settings.slippage_bps >= 0
    assert settings.api_key is None
    assert settings.admin_api_key is None
    assert settings.database_url is None
    assert settings.rate_limit_per_minute > 0
    assert settings.live_broker_endpoint is None
    assert settings.live_broker_key_id is None
    assert settings.live_broker_token is None
    assert settings.live_broker_provider == "generic-rest"
