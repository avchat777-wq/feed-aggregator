"""Avito New Developments lookup service.

Parses the official Avito directory XML (https://autoload.avito.ru/format/New_developments.xml)
and provides fast in-memory lookup by NewDevelopmentId.

Structure of the XML:
  <Developments>
    <Region name="...">
      <City name="...">
        <Object id="..." name="ЖК name" address="..." developer="...">
          <Housing id="..." name="Corpus name" address="..."/>
        </Object>

In Avito feeds, <NewDevelopmentId> can be either:
  - Object id  → jk_name = Object.name, address = Object.address
  - Housing id → jk_name = parent Object.name, house_name = Housing.name, address = Housing.address
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)

AVITO_DEV_FILE = Path("/app/data/avito_developments.xml")
AVITO_DEV_URL = "https://autoload.avito.ru/format/New_developments.xml"


@dataclass
class AvitoJkInfo:
    jk_name: str
    house_name: Optional[str]   # set only when id is a Housing id
    address: Optional[str]
    developer: Optional[str]
    city: Optional[str]


class AvitoLookup:
    """Singleton that loads Avito developments XML and resolves ids to JK info."""

    _instance: Optional["AvitoLookup"] = None
    _lookup: dict[str, AvitoJkInfo]
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lookup = {}
            cls._instance._loaded = False
        return cls._instance

    # ── Loading ────────────────────────────────────────────────────────────────

    def load_from_file(self, path: Path | str | None = None) -> int:
        """Load lookup from local XML file. Returns number of entries loaded."""
        path = Path(path) if path else AVITO_DEV_FILE
        if not path.exists():
            logger.warning(f"Avito developments file not found: {path}")
            return 0
        with open(path, "rb") as f:
            return self.load_from_bytes(f.read())

    def load_from_bytes(self, data: bytes) -> int:
        """Parse XML bytes and rebuild lookup table."""
        try:
            root = etree.fromstring(data)
        except etree.XMLSyntaxError as e:
            logger.error(f"AvitoLookup: invalid XML: {e}")
            return 0

        lookup: dict[str, AvitoJkInfo] = {}

        for region in root:
            region_name = region.get("name", "")
            for city in region:
                city_name = city.get("name", "")
                for obj in city.findall("Object"):
                    oid = obj.get("id", "")
                    jk_name = obj.get("name", "")
                    address = obj.get("address") or None
                    developer = obj.get("developer") or None

                    # Object id → full JK info (no house_name)
                    if oid:
                        lookup[oid] = AvitoJkInfo(
                            jk_name=jk_name,
                            house_name=None,
                            address=address,
                            developer=developer,
                            city=city_name,
                        )

                    # Housing id → JK from parent, house_name from Housing
                    for housing in obj.findall("Housing"):
                        hid = housing.get("id", "")
                        if hid:
                            lookup[hid] = AvitoJkInfo(
                                jk_name=jk_name,
                                house_name=housing.get("name") or None,
                                address=housing.get("address") or address,
                                developer=developer,
                                city=city_name,
                            )

        self._lookup = lookup
        self._loaded = True
        logger.info(f"AvitoLookup: loaded {len(lookup)} entries")
        return len(lookup)

    # ── Lookup ─────────────────────────────────────────────────────────────────

    def get(self, development_id: str | int | None) -> Optional[AvitoJkInfo]:
        """Resolve NewDevelopmentId to JK info. Returns None if not found or not loaded."""
        if not development_id or not self._loaded:
            return None
        return self._lookup.get(str(development_id))

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def entry_count(self) -> int:
        return len(self._lookup)

    # ── Persistence ────────────────────────────────────────────────────────────

    def save_to_disk(self, data: bytes) -> Path:
        """Save raw XML bytes to disk for persistence across restarts."""
        AVITO_DEV_FILE.parent.mkdir(parents=True, exist_ok=True)
        AVITO_DEV_FILE.write_bytes(data)
        logger.info(f"AvitoLookup: saved {len(data)} bytes to {AVITO_DEV_FILE}")
        return AVITO_DEV_FILE

    def try_autoload(self):
        """Try to load from disk on startup if file exists."""
        if AVITO_DEV_FILE.exists():
            count = self.load_from_file(AVITO_DEV_FILE)
            if count:
                logger.info(f"AvitoLookup: auto-loaded {count} entries from {AVITO_DEV_FILE}")


# Global singleton
avito_lookup = AvitoLookup()
