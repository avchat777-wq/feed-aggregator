"""Base parser interface and RawObject dataclass."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RawObject:
    """Raw parsed object before normalization.

    All values are strings at this stage — normalization converts them
    to proper types later.
    """
    source_object_id: str = ""
    developer_name: str = ""
    jk_name: str = ""
    jk_id_cian: Optional[str] = None
    house_name: Optional[str] = None
    section_number: Optional[str] = None
    flat_number: str = ""
    floor: str = ""
    floors_total: Optional[str] = None
    rooms: str = ""
    total_area: str = ""
    living_area: Optional[str] = None
    kitchen_area: Optional[str] = None
    price: str = ""
    price_per_sqm: Optional[str] = None
    sale_type: Optional[str] = None
    decoration: Optional[str] = None
    is_euro: Optional[str] = None
    is_apartments: Optional[str] = None
    description: Optional[str] = None
    photos: list[str] = field(default_factory=list)
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    phone: str = ""
    status: str = "active"
    address: Optional[str] = None  # raw address for fallback parsing


class BaseParser(ABC):
    """Abstract base class for all feed parsers.

    Each parser implements `parse()` that returns a list of RawObject.
    Parsers must be resilient: invalid XML, empty data, network issues
    should be caught and logged — never crash the whole sync cycle.
    """

    def __init__(self, source_config: dict):
        """
        Args:
            source_config: dict with source row fields (url, mapping_config, etc.)
        """
        self.source_config = source_config
        self.source_name = source_config.get("name", "unknown")
        self.errors: list[str] = []

    @abstractmethod
    def parse(self, content: bytes) -> list[RawObject]:
        """Parse raw content bytes into a list of RawObject.

        Args:
            content: raw bytes of the feed (XML, Excel, CSV)

        Returns:
            List of RawObject instances.
        """
        ...

    def _log_error(self, msg: str):
        """Record a non-fatal parse error."""
        logger.warning(f"[{self.source_name}] {msg}")
        self.errors.append(msg)
