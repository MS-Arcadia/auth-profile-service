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
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Kafka ---
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_user_events: str = "user-events"
    kafka_topic_gift_card_abuse: str = "gift-card-abuse-events"
    kafka_topic_ownership: str = "ownership-events"
    kafka_topic_item_granted: str = "item-events"
    kafka_topic_post_reacted: str = "post-events"
    kafka_topic_presence: str = "presence-events"
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
