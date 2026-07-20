import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    allowed_users: list[str] = field(default_factory=lambda: [
        u.strip() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()
    ])
    max_usage_per_user: int = field(
        default_factory=lambda: int(os.getenv("MAX_USAGE_PER_USER", "5"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    temp_dir: str = field(default_factory=lambda: os.getenv("TEMP_DIR", "./temp"))


settings = Settings()
