import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    panel_url: str = os.getenv("PANEL_URL", "").rstrip("/")
    panel_api_token: str = os.getenv("PANEL_API_TOKEN", "")
    panel_username: str = os.getenv("PANEL_USERNAME", "")
    panel_password: str = os.getenv("PANEL_PASSWORD", "")
    db_path: str = os.getenv("DB_PATH", "bot.db")
    card_number: str = os.getenv("CARD_NUMBER", "")
    plan_500_price: int = int(os.getenv("PLAN_500_PRICE", "485000"))
    plan_1000_price: int = int(os.getenv("PLAN_1000_PRICE", "970000"))
    admin_ids: tuple[int, ...] = tuple(
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
    )

config = Config()
