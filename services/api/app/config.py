from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trading Assistant API"
    environment: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    database_url: str = "sqlite:///./trading.db"
    redis_url: str = "redis://localhost:6379/0"

    # Alpaca
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"
    alpaca_feed: str = "iex"

    # Watchlist
    watchlist_stocks: str = "AAPL,NVDA,TSLA,SPY,QQQ"
    watchlist_crypto: str = "BTC/USD,ETH/USD"
    scan_interval_seconds: int = 60
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    demo_mode: bool = False

    # Notifications
    notify_webhook_url: str = ""
    notify_email_to: str = ""
    notify_smtp_host: str = "smtp.gmail.com"
    notify_smtp_port: int = 587
    notify_smtp_user: str = ""
    notify_smtp_password: str = ""
    notify_smtp_tls: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
