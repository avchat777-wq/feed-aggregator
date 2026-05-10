"""Development ID mapping service.

In-memory lookup: NewDevelopmentId → jk_name.
Priority 3 in the parser chain (after avito_lookup, before mapping_config).

Loaded from DB at startup and reloaded after any admin save.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DevIdMappingService:
    """Singleton in-memory lookup: development_id → jk_name."""

    _instance: Optional["DevIdMappingService"] = None
    _lookup: dict[str, str]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lookup = {}
        return cls._instance

    # ── Loading ────────────────────────────────────────────────────────────────

    async def reload(self, session) -> int:
        """Reload lookup from DB. Call after any save/delete."""
        from sqlalchemy import select
        from app.models.development_mapping import DevelopmentIdMapping

        result = await session.execute(select(DevelopmentIdMapping))
        rows = result.scalars().all()

        self._lookup = {row.development_id: row.jk_name for row in rows}
        logger.info(f"DevIdMappingService: loaded {len(self._lookup)} mappings")
        return len(self._lookup)

    def load_from_list(self, items: list[dict]) -> int:
        """Load from list of {development_id, jk_name} dicts (for startup)."""
        self._lookup = {item["development_id"]: item["jk_name"] for item in items}
        logger.info(f"DevIdMappingService: loaded {len(self._lookup)} mappings")
        return len(self._lookup)

    # ── Lookup ─────────────────────────────────────────────────────────────────

    def get(self, development_id: str | int | None) -> Optional[str]:
        """Return jk_name override for a development_id, or None."""
        if not development_id:
            return None
        return self._lookup.get(str(development_id))

    @property
    def count(self) -> int:
        return len(self._lookup)


# Global singleton
dev_id_mapping = DevIdMappingService()
