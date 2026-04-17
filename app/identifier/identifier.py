"""Identification and deduplication engine.

Per ТЗ section 8 — 4-step algorithm:

Step 1: Exact match by composite key (source_id + jk_name + house_name + flat_number).
Step 2: Fuzzy match (renumbering detection) — same source, floor, area ±0.5, rooms.
Step 3: Critical divergence — multiple candidates or area diff > 2 sqm → new object.
Step 4: New object — no match found → create with new ExternalId.

ExternalId format: {DEV_CODE}-{JK_CODE}-{SEQ}
ExternalId is immutable once assigned.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.object import Object, ObjectHistory
from app.normalizer.normalizer import UnifiedObject

logger = logging.getLogger(__name__)


class IdentificationResult:
    """Result of identifying a single object."""
    def __init__(self):
        self.action: str = ""  # "matched", "fuzzy_matched", "created", "diverged"
        self.object_id: Optional[int] = None
        self.external_id: str = ""
        self.changes: list[dict] = []
        self.old_flat_number: Optional[str] = None


class IdentificationEngine:
    """Handles object identification and deduplication."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def identify_and_upsert(self, unified: UnifiedObject) -> IdentificationResult:
        """Run the 4-step identification algorithm for one object."""
        result = IdentificationResult()

        # Step 1: Exact match
        existing = await self._find_exact_match(unified)
        if existing:
            result.action = "matched"
            result.object_id = existing.id
            result.external_id = existing.external_id
            result.changes = await self._update_object(existing, unified)
            return result

        # Step 2: Fuzzy match (renumbering)
        fuzzy = await self._find_fuzzy_match(unified)
        if fuzzy:
            if len(fuzzy) == 1:
                candidate = fuzzy[0]
                area_diff = abs(float(candidate.total_area) - float(unified.total_area))
                if area_diff <= 2.0:
                    result.action = "fuzzy_matched"
                    result.object_id = candidate.id
                    result.external_id = candidate.external_id
                    result.old_flat_number = candidate.flat_number
                    result.changes = await self._update_object(candidate, unified)
                    logger.info(
                        f"Renumbering detected: {candidate.flat_number} -> {unified.flat_number} "
                        f"(JK {unified.jk_name}, floor {unified.floor}, area {unified.total_area})"
                    )
                    return result

            # Step 3: Multiple candidates or large area difference → divergence
            result.action = "diverged"
            logger.warning(
                f"Critical divergence for {unified.developer_name}/{unified.jk_name}/"
                f"{unified.flat_number}: {len(fuzzy)} fuzzy candidates"
            )

        # Step 4: New object
        new_ext_id = await self._generate_external_id(unified)
        new_obj = self._create_object(unified, new_ext_id)
        self.session.add(new_obj)
        await self.session.flush()

        result.action = "created"
        result.object_id = new_obj.id
        result.external_id = new_ext_id
        return result

    async def _find_exact_match(self, u: UnifiedObject) -> Optional[Object]:
        """Step 1: exact composite key match."""
        stmt = select(Object).where(
            and_(
                Object.source_id == u.source_id,
                Object.jk_name == u.jk_name,
                Object.house_name == (u.house_name or ""),
                Object.flat_number == u.flat_number,
                Object.status != "removed",
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_fuzzy_match(self, u: UnifiedObject) -> list[Object]:
        """Step 2: fuzzy match — same source + floor + area ±0.5 + rooms."""
        area_low = u.total_area - Decimal("0.5")
        area_high = u.total_area + Decimal("0.5")

        stmt = select(Object).where(
            and_(
                Object.source_id == u.source_id,
                Object.jk_name == u.jk_name,
                Object.floor == u.floor,
                Object.rooms == u.rooms,
                Object.total_area >= area_low,
                Object.total_area <= area_high,
                Object.status != "removed",
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _update_object(self, obj: Object, u: UnifiedObject) -> list[dict]:
        """Update existing object fields and record history for changes."""
        changes = []
        now = datetime.now(timezone.utc)

        field_map = {
            "flat_number": u.flat_number,
            "floor": u.floor,
            "floors_total": u.floors_total,
            "rooms": u.rooms,
            "total_area": u.total_area,
            "living_area": u.living_area,
            "kitchen_area": u.kitchen_area,
            "price": u.price,
            "price_per_sqm": u.price_per_sqm,
            "sale_type": u.sale_type,
            "decoration": u.decoration,
            "is_euro": u.is_euro,
            "is_apartments": u.is_apartments,
            "description": u.description,
            "photos": u.photos,
            "phone": u.phone,
            "status": u.status,
            "source_object_id": u.source_object_id,
        }

        for field_name, new_value in field_map.items():
            old_value = getattr(obj, field_name)
            # Compare with type coercion
            if str(old_value) != str(new_value) and new_value is not None:
                change = {
                    "field": field_name,
                    "old": str(old_value),
                    "new": str(new_value),
                }
                changes.append(change)

                # Record in history
                history = ObjectHistory(
                    object_id=obj.id,
                    field_name=field_name,
                    old_value=str(old_value),
                    new_value=str(new_value),
                    changed_at=now,
                )
                self.session.add(history)
                setattr(obj, field_name, new_value)

        obj.last_seen_at = now
        obj.missing_count = 0
        obj.hash = u.hash

        return changes

    async def _generate_external_id(self, u: UnifiedObject) -> str:
        """Generate stable ExternalId: {DEV_CODE}-{JK_CODE}-{SEQ}."""
        dev_code = self._make_code(u.developer_name)
        jk_code = self._make_code(u.jk_name)
        prefix = f"{dev_code}-{jk_code}"

        # Find max sequence number for this prefix
        stmt = select(func.count()).where(
            Object.external_id.like(f"{prefix}-%")
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        seq = str(count + 1).zfill(5)
        return f"{prefix}-{seq}"

    @staticmethod
    def _make_code(name: str) -> str:
        """Convert a name to a short code for ExternalId."""
        # Transliterate Cyrillic
        translit = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
            "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
            "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
            "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
            "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
            "э": "e", "ю": "yu", "я": "ya",
        }
        result = []
        for ch in name.lower():
            if ch in translit:
                result.append(translit[ch])
            elif ch.isalnum():
                result.append(ch)
            elif ch in " -_":
                result.append("-")

        code = "".join(result).upper()
        code = re.sub(r"-+", "-", code).strip("-")
        # Limit length
        return code[:30] if len(code) > 30 else code

    @staticmethod
    def _create_object(u: UnifiedObject, external_id: str) -> Object:
        """Create a new Object model instance."""
        return Object(
            external_id=external_id,
            source_id=u.source_id,
            source_object_id=u.source_object_id,
            developer_name=u.developer_name,
            jk_name=u.jk_name,
            jk_id_cian=u.jk_id_cian,
            house_name=u.house_name or "",
            section_number=u.section_number,
            flat_number=u.flat_number,
            floor=u.floor,
            floors_total=u.floors_total,
            rooms=u.rooms,
            total_area=u.total_area,
            living_area=u.living_area,
            kitchen_area=u.kitchen_area,
            price=u.price,
            price_per_sqm=u.price_per_sqm,
            sale_type=u.sale_type,
            decoration=u.decoration,
            is_euro=u.is_euro,
            is_apartments=u.is_apartments,
            description=u.description,
            photos=u.photos,
            latitude=u.latitude,
            longitude=u.longitude,
            phone=u.phone,
            status=u.status,
            hash=u.hash,
            missing_count=0,
        )

    async def handle_missing_objects(self, source_id: int,
                                     seen_object_ids: set[int]) -> list[int]:
        """Handle objects present in DB but absent from current feed.

        Per ТЗ 8.4:
        - 1st miss: missing_count=1, keep in feed
        - 2nd miss: missing_count=2, keep in feed
        - 3rd miss: status=removed, exclude from feed
        """
        stmt = select(Object).where(
            and_(
                Object.source_id == source_id,
                Object.status != "removed",
                Object.id.not_in(seen_object_ids) if seen_object_ids else True,
            )
        )
        result = await self.session.execute(stmt)
        missing_objects = list(result.scalars().all())
        removed_ids = []

        for obj in missing_objects:
            if obj.id in seen_object_ids:
                continue

            obj.missing_count = (obj.missing_count or 0) + 1

            if obj.missing_count >= 3:
                obj.status = "removed"
                obj.removed_at = datetime.now(timezone.utc)
                removed_ids.append(obj.id)
                logger.info(
                    f"Object removed after 3 misses: {obj.external_id} "
                    f"({obj.jk_name}, кв. {obj.flat_number})"
                )

        return removed_ids
