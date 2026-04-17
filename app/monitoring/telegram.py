"""Telegram notification module.

Per ТЗ section 10 — sends alerts for:
- CRITICAL: source unavailable, 0 objects, feed generation error
- WARNING: object count drop >20%, mass price change >15%, parse errors
- INFO: successful sync summary, renumbering events
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.alert import Alert

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    def __init__(self, session: AsyncSession | None = None):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.session = session
        self.enabled = bool(self.token and self.chat_id)

    async def send(self, message: str, level: str = "INFO") -> bool:
        """Send a message to the configured Telegram chat.

        Args:
            message: Text of the notification.
            level: CRITICAL, WARNING, or INFO.

        Returns:
            True if sent successfully.
        """
        if not self.enabled:
            logger.warning("Telegram not configured, skipping notification")
            return False

        # Prepend level emoji
        emoji = {"CRITICAL": "\u26a0\ufe0f", "WARNING": "\u26a0", "INFO": "\u2139\ufe0f"}.get(level, "")
        full_message = f"{emoji} [{level}] {message}"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": full_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        response_text = ""
        success = False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                response_text = resp.text
                success = resp.status_code == 200
                if not success:
                    logger.error(f"Telegram API error: {resp.status_code} {response_text}")
        except Exception as e:
            response_text = str(e)
            logger.error(f"Telegram send failed: {e}")

        # Log to database
        if self.session:
            alert = Alert(
                type=level,
                message=message,
                sent_at=datetime.now(timezone.utc),
                telegram_response=response_text[:500],
            )
            self.session.add(alert)

        return success

    # ─────────────── Convenience methods for specific event types ───────────────

    async def notify_source_unavailable(self, name: str, url: str, error: str):
        await self.send(
            f'Feed/file of developer "<b>{name}</b>" is unavailable.\n'
            f"URL: {url}\nError: {error}",
            level="CRITICAL",
        )

    async def notify_empty_source(self, name: str, prev_count: int):
        await self.send(
            f'Feed "<b>{name}</b>" returned 0 objects.\n'
            f"Previous sync: {prev_count} objects.",
            level="CRITICAL",
        )

    async def notify_object_drop(self, name: str, old_count: int, new_count: int, pct: float):
        await self.send(
            f'Source "<b>{name}</b>": object count dropped by {pct:.0f}% '
            f"({old_count} → {new_count}). Threshold: {settings.threshold_drop_warning}%.",
            level="WARNING",
        )

    async def notify_mass_price_change(self, name: str, count: int, pct: float):
        await self.send(
            f'Source "<b>{name}</b>": {count} objects ({pct:.0f}%) had price changes > '
            f"{settings.threshold_price_change_min}%.",
            level="WARNING",
        )

    async def notify_parse_errors(self, name: str, skipped: int, errors: list[str]):
        details = "\n".join(errors[:5])
        await self.send(
            f'Parsing "<b>{name}</b>": {skipped} objects skipped.\nDetails:\n{details}',
            level="WARNING",
        )

    async def notify_renumbering(self, old_num: str, new_num: str, jk: str,
                                  floor: int, area):
        await self.send(
            f"Renumbering: apt. {old_num} → {new_num} "
            f"(JK {jk}, floor {floor}, {area} m²).",
            level="INFO",
        )

    async def notify_sync_complete(self, sources: int, total: int,
                                    new: int, updated: int, removed: int):
        await self.send(
            f"Sync complete.\nSources: {sources}. Objects: {total}.\n"
            f"New: {new}. Updated: {updated}. Removed: {removed}.",
            level="INFO",
        )

    async def notify_feed_generation_error(self, error: str):
        await self.send(
            f"Failed to generate feed.\nError: {error}\n"
            "Previous version preserved.",
            level="CRITICAL",
        )
