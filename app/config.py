from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "auth-profile-service"
    env: str = "local"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://arcadia:arcadia@localhost:5432/auth_profile_db"
    sql_echo: bool = False

    # --- JWT ---
    # Must match JWT_SECRET on every other service — they verify what this one signs.
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    # Required claims, not decoration. Every service on the platform verifies both, and a token
    # without them is rejected by all five — which is what this service used to emit.
    jwt_issuer: str = "arcadia-auth"
    jwt_audience: str = "arcadia"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Kafka ---
    kafka_bootstrap_servers: str = "localhost:9092"
    # The platform's real topic names. These were invented per event — `ownership-events`,
    # `gift-card-abuse-events` — and none of them existed, so four of the five consumers were
    # subscribed to topics nothing ever published to.
    #
    # A topic here is per *producer*, not per event: `wallet-events` is every balance movement on
    # the platform and `game-events` is every catalog change, so the handlers route on event_type
    # rather than processing whatever arrives.
    kafka_topic_user_events: str = "user-events"
    kafka_topic_wallet_events: str = "wallet-events"
    kafka_topic_game_events: str = "game-events"
    # Marketplace and Community do not exist yet. Named to match the convention so those consumers
    # start working the day those services ship.
    kafka_topic_trade_events: str = "trade-events"
    kafka_topic_community_events: str = "community-events"
    kafka_consumer_group: str = "auth-profile-service"

    # --- Outbox dispatcher ---
    outbox_poll_interval_seconds: float = 2.0
    outbox_batch_size: int = 50

    # --- Presence ---
    presence_ttl_seconds: int = 30

    # --- Rate limiting ---
    rate_limit_login: str = "10/minute"
    rate_limit_register: str = "5/minute"

    # --- Observability ---
    otel_exporter_otlp_endpoint: str = ""  
    enable_metrics: bool = True

    # --- Super Admin bootstrap (seeded on first startup if not present) ---
    super_admin_email: str = "admin@arcadia.com"
    super_admin_password: str = "ChangeMe123!"
    super_admin_display_name: str = "Super Admin"


settings = Settings()
