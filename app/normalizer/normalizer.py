"""Normalization module — converts RawObject to UnifiedObject.

Rules per ТЗ section 7.2:
- Areas: numeric with dot separator, round to 1 decimal
- Prices: integer rubles, detect "тыс. руб" -> *1000
- Floors: integer, validate > 0 and <= floors_total
- Rooms: "студия"/"studio"/"ст" -> 0, "свободная планировка" -> 0, 7+ -> 9
- Phones: format 79XXXXXXXXX, strip +7/8 prefix
- Decoration: synonym mapping -> without/rough/fine/turnkey
- Sale type: ДДУ/214-ФЗ -> DDU, переуступка/цессия -> assignment
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.parsers.base import RawObject

logger = logging.getLogger(__name__)


@dataclass
class UnifiedObject:
    """Normalized object with proper types."""
    source_id: int = 0
    source_object_id: str = ""
    developer_name: str = ""
    jk_name: str = ""
    jk_id_cian: Optional[int] = None
    house_name: Optional[str] = None
    section_number: Optional[str] = None
    flat_number: str = ""
    floor: int = 0
    floors_total: Optional[int] = None
    rooms: int = 0
    total_area: Decimal = Decimal("0")
    living_area: Optional[Decimal] = None
    kitchen_area: Optional[Decimal] = None
    price: int = 0
    price_per_sqm: Optional[int] = None
    sale_type: Optional[str] = None
    decoration: Optional[str] = None
    is_euro: Optional[bool] = None
    is_apartments: Optional[bool] = None
    address: Optional[str] = None
    description: Optional[str] = None
    photos: list[str] = field(default_factory=list)
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    phone: str = ""
    status: str = "active"
    hash: str = ""
    object_type: str = "квартира"  # квартира / кладовка / машиноместо / апартаменты


# ──────────────────────────── Synonym tables ────────────────────────────

DECORATION_MAP = {
    "без отделки": "without",
    "предчистовая": "without",
    "черновая": "rough",
    "черновой": "rough",
    "чистовая": "fine",
    "white box": "fine",
    "вайт бокс": "fine",
    "под ключ": "turnkey",
    "с мебелью": "turnkey",
    "чистовая с мебелью": "turnkey",
    "without": "without",
    "rough": "rough",
    "fine": "fine",
    "turnkey": "turnkey",
}

SALE_TYPE_MAP = {
    "дду": "DDU",
    "214-фз": "DDU",
    "договор долевого участия": "DDU",
    "переуступка": "assignment",
    "цессия": "assignment",
    "пдкп": "pdkp",
    "предварительный договор": "pdkp",
    "ddu": "DDU",
    "assignment": "assignment",
    "pdkp": "pdkp",
}

ROOMS_STUDIO_SYNONYMS = {"студия", "studio", "ст", "ст.", "свободная планировка", "свободная"}


# ──────────────────────────── Core normalization ────────────────────────────

def normalize_object(
    raw: RawObject,
    source_id: int,
    phone_override: Optional[str] = None,
    jk_synonyms: Optional[dict[str, str]] = None,
) -> UnifiedObject:
    """Convert a RawObject into a fully normalized UnifiedObject.

    Args:
        raw: Parsed raw object from any parser.
        source_id: Database ID of the source.
        phone_override: If set, replaces the phone from the feed.
        jk_synonyms: Optional {raw_name_lower: canonical_name} dict for JK
                     name normalisation.  Built by the scheduler from the
                     jk_synonyms DB table.
    """
    u = UnifiedObject()
    u.source_id = source_id
    u.source_object_id = raw.source_object_id.strip()
    u.developer_name = raw.developer_name.strip()

    # Apply JK synonym normalization
    raw_jk = raw.jk_name.strip()
    if jk_synonyms and raw_jk:
        u.jk_name = jk_synonyms.get(raw_jk.lower(), raw_jk)
    else:
        u.jk_name = raw_jk
    u.jk_id_cian = _parse_int(raw.jk_id_cian)
    u.house_name = raw.house_name.strip() if raw.house_name else None
    u.section_number = raw.section_number.strip() if raw.section_number else None
    u.flat_number = raw.flat_number.strip()
    u.floor = _normalize_floor(raw.floor)
    u.floors_total = _parse_int(raw.floors_total)
    u.rooms = _normalize_rooms(raw.rooms)
    u.total_area = _normalize_area(raw.total_area)
    u.living_area = _normalize_area(raw.living_area) if raw.living_area else None
    u.kitchen_area = _normalize_area(raw.kitchen_area) if raw.kitchen_area else None
    u.price = _normalize_price(raw.price)
    u.sale_type = _normalize_sale_type(raw.sale_type)
    u.decoration = _normalize_decoration(raw.decoration)
    u.is_euro = _parse_bool(raw.is_euro)
    u.is_apartments = _parse_bool(raw.is_apartments)
    u.address = raw.address.strip() if raw.address else None
    u.description = raw.description.strip() if raw.description else None
    u.photos = [url for url in raw.photos if url.startswith("http")]
    u.latitude = _parse_decimal(raw.latitude)
    u.longitude = _parse_decimal(raw.longitude)
    u.object_type = (raw.object_type or "квартира").strip().lower()
    u.phone = _normalize_phone(phone_override or raw.phone)
    u.status = raw.status.strip().lower() if raw.status else "active"

    # Auto-calculate price per sqm
    if u.price > 0 and u.total_area > 0:
        u.price_per_sqm = int(u.price / float(u.total_area))

    # Validate floor
    if u.floors_total and u.floor > u.floors_total:
        logger.warning(
            f"Floor {u.floor} > total floors {u.floors_total} for "
            f"{u.developer_name}/{u.jk_name}/{u.flat_number}"
        )

    # Compute hash for change detection
    u.hash = _compute_hash(u)

    return u


# ──────────────────────────── Field normalizers ────────────────────────────

def _normalize_area(raw: Optional[str]) -> Decimal:
    """Parse area to Decimal with 1 decimal place."""
    if not raw:
        return Decimal("0")
    # Remove units first (кв.м, м², sqm, кв. м etc.)
    cleaned = re.sub(r"(кв\.?\s*м²?|м²|sqm|sq\.?\s*m)", "", raw.strip(), flags=re.IGNORECASE)
    # Then keep only digits, dots, commas
    cleaned = re.sub(r"[^\d.,]", "", cleaned)
    cleaned = cleaned.replace(",", ".").strip(".")
    # Handle multiple dots (e.g. "65.5." -> "65.5")
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = parts[0] + "." + parts[1]
    try:
        return Decimal(cleaned).quantize(Decimal("0.1"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _normalize_price(raw: Optional[str]) -> int:
    """Parse price to integer rubles. Detect 'тыс' (thousands)."""
    if not raw:
        return 0
    raw_lower = raw.lower().strip()
    multiplier = 1

    if "тыс" in raw_lower or "т.р" in raw_lower:
        multiplier = 1000
    elif "млн" in raw_lower:
        multiplier = 1_000_000

    # Remove everything except digits and dots/commas
    cleaned = re.sub(r"[^\d.,]", "", raw_lower)
    cleaned = cleaned.replace(",", ".").rstrip(".")

    try:
        value = float(cleaned) * multiplier
        return int(round(value))
    except (ValueError, TypeError):
        return 0


def _normalize_floor(raw: Optional[str]) -> int:
    """Parse floor to positive integer."""
    val = _parse_int(raw)
    return max(val, 0)


def _normalize_rooms(raw: Optional[str]) -> int:
    """Normalize room count: studio -> 0, 7+ -> 9, numbers as-is."""
    if not raw:
        return 0
    raw_lower = raw.strip().lower()

    if raw_lower in ROOMS_STUDIO_SYNONYMS:
        return 0

    # Extract first number
    match = re.search(r"\d+", raw_lower)
    if not match:
        return 0

    rooms = int(match.group())
    if rooms >= 7:
        return 9  # "многокомнатная"
    return rooms


def _normalize_phone(raw: Optional[str]) -> str:
    """Normalize phone to 79XXXXXXXXX format (11 digits)."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 11:
        if digits.startswith("8"):
            digits = "7" + digits[1:]
        elif digits.startswith("7"):
            pass
        return digits
    elif len(digits) == 10:
        return "7" + digits
    elif len(digits) > 11:
        # Try stripping country code
        if digits.startswith("7") or digits.startswith("8"):
            return "7" + digits[-10:]

    return digits


def _normalize_decoration(raw: Optional[str]) -> Optional[str]:
    """Map decoration synonyms to standard values."""
    if not raw:
        return None
    return DECORATION_MAP.get(raw.strip().lower())


def _normalize_sale_type(raw: Optional[str]) -> Optional[str]:
    """Map sale type synonyms to standard values."""
    if not raw:
        return None
    return SALE_TYPE_MAP.get(raw.strip().lower())


# ──────────────────────────── Utilities ────────────────────────────

def _parse_int(raw: Optional[str]) -> int:
    if not raw:
        return 0
    match = re.search(r"\d+", raw.strip())
    return int(match.group()) if match else 0


def _parse_decimal(raw: Optional[str]) -> Optional[Decimal]:
    if not raw:
        return None
    try:
        return Decimal(raw.strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _parse_bool(raw: Optional[str]) -> Optional[bool]:
    if not raw:
        return None
    raw_lower = raw.strip().lower()
    if raw_lower in ("true", "1", "да", "yes"):
        return True
    if raw_lower in ("false", "0", "нет", "no"):
        return False
    return None


def _compute_hash(u: UnifiedObject) -> str:
    """SHA256 hash of key fields for change detection."""
    data = "|".join([
        str(u.jk_name), str(u.house_name), str(u.flat_number),
        str(u.floor), str(u.rooms), str(u.total_area),
        str(u.price), str(u.status), str(u.decoration),
        str(u.sale_type), str(u.phone),
    ])
    return hashlib.sha256(data.encode()).hexdigest()
