"""Telegram Dispatcher for News Intelligence Calls."""
import logging
from typing import Optional
from src.models import ClassifiedNews

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, enabled: bool = False):
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""
        self.enabled = enabled and bool(self.bot_token and self.chat_id)

    def send_call(self, news: ClassifiedNews) -> bool:
        if not self.enabled:
            return False

        try:
            import requests

            import html

            direction = "NEUTRAL"
            score = 0.0
            if news.impacts:
                direction = news.impacts[0].direction.upper()
                score = news.impacts[0].score

            emoji = "🟢" if direction == "POSITIVE" else "🔴" if direction == "NEGATIVE" else "⚪"
            branches = ", ".join(f"#{b.branch}" for b in news.branches) or "#general"
            pub_time = news.item.published_at or "N/A"

            translation_block = ""
            if news.item.lang == "en" and news.item.title_ru:
                escaped_ru = html.escape(news.item.title_ru)
                translation_block = f"🇷🇺 <i>{escaped_ru}</i>\n\n"

            escaped_title = html.escape(news.item.title)

            text = (
                f"{emoji} <b>[MARKET CALL: {direction}]</b>\n\n"
                f"<b>{escaped_title}</b>\n\n"
                f"{translation_block}"
                f"🕒 <b>Published:</b> {pub_time}\n"
                f"🏢 <b>Sectors:</b> {branches}\n"
                f"📊 <b>Score:</b> {score:+.2f}\n"
                f"📰 <b>Source:</b> {news.item.source.upper()}\n"
                f"🔗 <a href='{news.item.url}'>Read source article</a>"
            )

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to dispatch Telegram alert: {e}")
            return False
