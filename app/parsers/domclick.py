"""Parser for DomClick (Домклик) XML feed format.

Handles all DomClick-compatible variants from real estate platforms:
- barnaul-gi.ru/DomClick.xml          — Жилищная Инициатива
- domoplaner.ru/dc-api/feeds/...       — Мой дом, СибКомИнвест, Век-строй
- profitbase.ru/export/domclick/...    — Адалин-Строй
- dsi.vtcrm.ru/xmlgen/DomclickNov...   — ДС-Инвестстрой (Чайка)
- alg22.ru/domclick/xml.php            — Алгоритм
- macroserver.ru/.../domclickpro/...   — ВОТЭТОДОМ

All variants share the same <feed><object> or <objects><object> root structure
with different field name capitalization conventions.  Each field is tried
against an ordered list of candidate tag names — first match wins.
"""

from __future__ import annotations

import logging
from lxml import etree
from app.parsers.base import BaseParser, RawObject

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Candidate tag names for each logical field (tried in order, first found wins)
# ──────────────────────────────────────────────────────────────────────────────
FIELD_CANDIDATES: dict[str, list[str]] = {
    "id": [
        "id", "Id", "ID",
        "flat_id", "FlatId", "flatId",          # domoplaner.ru
        "object_id", "objectId", "ObjectId",
        "apartment_id", "ApartmentId",
    ],
    "type": [
        "type", "Type", "TYPE",
        "object_type", "ObjectType",
    ],
    "status": [
        "status", "Status", "STATUS",
    ],
    "jk_name": [
        # most common DomClick tag
        "newbuilding", "NewBuilding", "new_building",
        # alternative naming
        "complex_name", "ComplexName", "complex",
        "jk", "JK", "jk_name",
        "ResidentialComplex", "residential_complex",
        "building_complex", "BuildingComplex",
        # domoplaner / profitbase variants
        "NewDevelopmentName", "newDevelopmentName",
        "project", "Project", "project_name", "ProjectName",
        "realty_developer", "object_name", "ObjectName",
        "complex_title", "ComplexTitle",
        "housing_complex", "HousingComplex",
        "жк", "ЖК", "название_жк",
    ],
    "jk_id": [
        "newbuilding_id", "newbuildingId", "NewBuildingId",
        "complex_id", "jk_id",
    ],
    "house_name": [
        "house", "House", "HOUSE",
        "building", "Building",
        "corpus", "Corpus",
        "liter", "Liter",
        "house_name", "HouseName",
        "building_name", "BuildingName",
        "block", "Block",
    ],
    "section": [
        "section", "Section",
        "porch", "Porch",
        "entrance", "Entrance",
        "section_number", "SectionNumber",
    ],
    "flat_number": [
        "flat_number", "FlatNumber", "flatNumber",
        "apartment_number", "ApartmentNumber",
        "apartment", "Apartment",               # domoplaner.ru
        "number", "Number",
        "flat", "Flat",
        "apt", "Apt",
    ],
    "floor": [
        "floor", "Floor", "FLOOR",
        "floor_number", "FloorNumber",
    ],
    "floors_total": [
        "floors_count", "FloorsCount", "floors_total",
        "floors", "Floors", "FLOORS",
        "total_floors", "TotalFloors",
        "storeys_count", "StoreysCount",
    ],
    "rooms": [
        "rooms_count", "RoomsCount",
        "rooms", "Rooms", "ROOMS",
        "room_count", "RoomCount",
        "room", "Room",                         # domoplaner.ru (singular)
        "rooms_number", "RoomsNumber",
    ],
    "total_area": [
        "area", "Area", "AREA",
        "total_area", "TotalArea",
        "square", "Square", "SQUARE",
        "full_area", "FullArea",
        "all_rooms_area", "AllRoomsArea",
        "AreaValue",
    ],
    "living_area": [
        "living_area", "LivingArea",
        "living_square", "LivingSquare",
        "residential_area", "ResidentialArea",
    ],
    "kitchen_area": [
        "kitchen_area", "KitchenArea",
        "kitchen_square", "KitchenSquare",
    ],
    "price": [
        "price", "Price", "PRICE",
        "cost", "Cost",
        "full_price", "FullPrice",
    ],
    "sale_type": [
        "sale_type", "SaleType",
        "deal_type", "DealType",
        "transaction_type", "TransactionType",
    ],
    "decoration": [
        "finish_type", "FinishType",
        "decoration", "Decoration",
        "finish", "Finish",
        "finishing", "Finishing",
        "repair", "Repair",
        "repair_type", "RepairType",
        "renovation", "Renovation",             # domoplaner.ru
    ],
    "description": [
        "description", "Description",
        "text", "Text",
        "comment", "Comment",
    ],
    "latitude": [
        "lat", "latitude", "Latitude", "LAT",
        "geo_lat", "geoLat",
    ],
    "longitude": [
        "lon", "lng", "longitude", "Longitude",
        "geo_lon", "geoLon",
    ],
}

# Values that mean "active" in status field
ACTIVE_STATUSES = {
    "active", "1", "true", "available",
    "активный", "активна", "активно",
    "в продаже", "free", "Free", "продается",
    "on_sale", "onsale",
}

# Values that mean "booked"
BOOKED_STATUSES = {
    "booked", "reserved", "забронировано",
    "бронь", "резерв",
}

# Values that mean "sold"
SOLD_STATUSES = {
    "sold", "продано", "продан", "продана",
    "closed", "0",
}

# DomClick finish_type values → normalizer-friendly
FINISH_TYPE_MAP = {
    # English variants
    "WhiteBox": "rough",
    "Whitebox": "rough",
    "white_box": "rough",
    "white box": "rough",
    "WithoutFinish": "without",
    "without_finish": "without",
    "Clean": "fine",
    "clean_finish": "fine",
    "Turnkey": "turnkey",
    "turnkey": "turnkey",
    # Russian variants (domoplaner.ru uses "renovation" field with Russian values)
    "предчистовая": "rough",
    "черновая": "without",
    "без отделки": "without",
    "чистовая": "fine",
    "под ключ": "turnkey",
    "отделка": "fine",
    "с отделкой": "fine",
}


class DomClickParser(BaseParser):
    """Parse DomClick-compatible XML feeds.

    Supports <feed><object> and <objects><object> root structures.
    Automatically detects field names for each platform variant.
    """

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError:
            # Try recovery parser for slightly broken feeds
            try:
                recover_parser = etree.XMLParser(recover=True)
                root = etree.fromstring(content, parser=recover_parser)
            except Exception as e:
                self._log_error(f"Invalid XML (recovery failed): {e}")
                return results

        # Try to extract JK name from root element attributes or child tags
        # (handles <complexes name="ЖК Название"> or <complexes><name>...</name>)
        root_jk_name = self._get_complex_name(root)

        # Strategy A: <complexes><complex><flat> structure
        # JK name is on the <complex> level, flats are children
        complexes = root.findall(".//complex") or root.findall(".//Complex")
        if complexes:
            for complex_elem in complexes:
                jk_name = self._get_complex_name(complex_elem)
                for flat_tag in ("flat", "Flat", "object", "Object", "offer", "Offer"):
                    flats = complex_elem.findall(flat_tag)
                    if flats:
                        for elem in flats:
                            try:
                                obj = self._parse_object(elem, jk_name_override=jk_name)
                                if self._is_valid(obj):
                                    results.append(obj)
                                else:
                                    self._log_error(
                                        f"Skipped flat id={self._get_field(elem, 'id')}: "
                                        "missing required fields"
                                    )
                            except Exception as e:
                                self._log_error(f"Error parsing flat: {e}")
                        break
            if results:
                logger.info(
                    f"[{self.source_name}] DomClick parser (complexes): "
                    f"{len(results)} objects parsed"
                )
                return results

        # Strategy B: flat object elements without complex wrapper
        # JK name fallback chain:
        #   1. Name extracted from root XML element (e.g. <feed name="ЖК Вышка">)
        #   2. mapping_config.jk_name — admin-specified override for feeds without JK in XML
        # NOTE: source "name" is intentionally NOT used — it is an admin label,
        #       not the residential complex name.
        mapping_jk = ""
        mc = self.source_config.get("mapping_config") or {}
        if isinstance(mc, dict):
            mapping_jk = mc.get("jk_name", "") or ""
        fallback_jk = root_jk_name or mapping_jk

        objects = self._find_objects(root)
        if not objects:
            self._log_error(
                f"No object elements found. Root tag: <{root.tag}>. "
                "Expected <feed><object>, <objects><object>, or <complexes><complex><flat>."
            )
            return results

        for elem in objects:
            try:
                obj = self._parse_object(elem, jk_name_override=fallback_jk)
                if self._is_valid(obj):
                    results.append(obj)
                else:
                    self._log_error(
                        f"Skipped object id={self._get_field(elem, 'id')}: "
                        "missing required fields (price, area, floor)"
                    )
            except Exception as e:
                self._log_error(f"Error parsing object: {e}")

        logger.info(f"[{self.source_name}] DomClick parser: {len(results)} objects parsed")
        return results

    # ── Finding objects ─────────────────────────────────────────────────────

    def _get_complex_name(self, complex_elem) -> str:
        """Extract JK name from a <complex> element."""
        for tag in (
            "name", "Name", "NAME",
            "complex_name", "ComplexName",
            "jk_name", "jk", "JK",
            "title", "Title",
            "newbuilding", "NewBuilding",
        ):
            el = complex_elem.find(tag)
            if el is not None and el.text:
                return el.text.strip()
            val = complex_elem.get(tag)
            if val:
                return val.strip()
        return ""

    def _find_objects(self, root) -> list:
        """Try multiple strategies to locate flat/object elements (non-complex feeds)."""
        # Strategy 1: direct children named 'object' or 'Object'
        candidates = root.findall("object") or root.findall("Object")
        if candidates:
            return candidates

        # Strategy 2: any descendant named 'object'
        candidates = root.findall(".//object") or root.findall(".//Object")
        if candidates:
            return candidates

        # Strategy 3: flat, offer, item variants
        for tag in ("offer", "Offer", "item", "Item", "flat", "Flat", "apartment", "Apartment"):
            candidates = root.findall(f".//{tag}")
            if candidates:
                return candidates

        return []

    # ── Per-object parsing ──────────────────────────────────────────────────

    def _parse_object(self, elem, jk_name_override: str = "") -> RawObject:
        obj = RawObject()
        g = lambda field: self._get_field(elem, field)

        obj.source_object_id = g("id")
        # Priority: field inside the object element → complex/root override
        # (override is used when objects live inside <complex> that carries the JK name)
        obj.jk_name         = g("jk_name") or jk_name_override
        obj.jk_id_cian      = g("jk_id") or None
        obj.house_name      = g("house_name") or None
        obj.section_number  = g("section") or None
        obj.flat_number     = g("flat_number") or obj.source_object_id
        obj.floor           = g("floor")
        obj.floors_total    = g("floors_total") or None
        obj.rooms           = self._normalize_rooms_raw(g("rooms"))
        obj.total_area      = g("total_area")
        obj.living_area     = g("living_area") or None
        obj.kitchen_area    = g("kitchen_area") or None
        obj.price           = g("price")
        obj.sale_type       = g("sale_type") or None
        obj.decoration      = self._map_decoration(g("decoration"))
        obj.description     = g("description") or None
        obj.latitude        = g("latitude") or None
        obj.longitude       = g("longitude") or None
        obj.status          = self._map_status(g("status"))

        # Developer name from source config
        obj.developer_name = self.source_config.get("developer_name", "")

        # Phone — look in <phones><phone> or direct tags
        obj.phone = self._extract_phone(elem)

        # Photos — look in <images><image> or <photos><photo>
        obj.photos = self._extract_photos(elem)

        return obj

    # ── Field extraction helpers ────────────────────────────────────────────

    def _get_field(self, elem, field_key: str) -> str:
        """Try all candidate tag names for the field, return first found."""
        for tag in FIELD_CANDIDATES.get(field_key, []):
            el = elem.find(tag)
            if el is not None and el.text:
                return el.text.strip()
            # Also check as attribute
            val = elem.get(tag)
            if val:
                return val.strip()
        return ""

    def _extract_phone(self, elem) -> str:
        """Extract phone from <phones><phone>, <phone>, or <contacts><phone>."""
        # Try <phones> container
        for phones_tag in ("phones", "Phones", "contacts", "Contacts"):
            phones = elem.find(phones_tag)
            if phones is not None:
                for phone_tag in ("phone", "Phone", "number", "Number"):
                    ph = phones.find(phone_tag)
                    if ph is not None and ph.text:
                        return ph.text.strip()

        # Try direct child tags
        for tag in ("phone", "Phone", "contact_phone", "ContactPhone", "tel", "Tel"):
            el = elem.find(tag)
            if el is not None and el.text:
                return el.text.strip()

        return self.source_config.get("phone_override", "")

    def _extract_photos(self, elem) -> list[str]:
        """Extract photo URLs from <images><image>, <photos><photo>, etc."""
        photos = []
        seen: set[str] = set()

        def add_url(url: str):
            url = url.strip()
            if url and url.startswith("http") and url not in seen:
                seen.add(url)
                photos.append(url)

        # Try <images> container
        for container_tag in ("images", "Images", "photos", "Photos", "gallery", "Gallery"):
            container = elem.find(container_tag)
            if container is not None:
                for child in container:
                    # tag might be <image>, <photo>, <item>, <url>
                    if child.text:
                        add_url(child.text)
                    # also check src, url attributes
                    for attr in ("src", "url", "href"):
                        val = child.get(attr)
                        if val:
                            add_url(val)
                if photos:
                    return photos

        # Try <image_url_1>, <image_url_2>, ... pattern
        for i in range(1, 20):
            for tag in (f"image_url_{i}", f"photo_{i}", f"img{i}"):
                el = elem.find(tag)
                if el is not None and el.text:
                    add_url(el.text)

        return photos

    # ── Normalization helpers ───────────────────────────────────────────────

    @staticmethod
    def _map_status(raw: str) -> str:
        lower = raw.lower().strip()
        if lower in ACTIVE_STATUSES:
            return "active"
        if lower in BOOKED_STATUSES:
            return "booked"
        if lower in SOLD_STATUSES:
            return "sold"
        # Default to active if unknown (new buildings rarely have other statuses in feeds)
        return "active" if raw else "active"

    @staticmethod
    def _map_decoration(raw: str) -> str | None:
        """Map DomClick finish_type to normalizer-compatible string."""
        if not raw:
            return None
        # Try direct lookup in DomClick map first
        mapped = FINISH_TYPE_MAP.get(raw.strip())
        if mapped:
            return mapped
        # Return as-is for normalizer to handle
        return raw.strip() if raw.strip() else None

    @staticmethod
    def _normalize_rooms_raw(raw: str) -> str:
        """Convert DomClick room types to numeric string."""
        if not raw:
            return "0"
        lower = raw.strip().lower()
        # DomClick uses "Studio" or "Студия" for studios
        if lower in ("studio", "студия", "ст", "0"):
            return "0"
        # "FreeLayout" / "свободная планировка"
        if "layout" in lower or "planning" in lower or "свободн" in lower:
            return "0"
        return raw.strip()

    @staticmethod
    def _is_valid(obj: RawObject) -> bool:
        """Check that mandatory fields are present."""
        return bool(
            obj.price and obj.price != "0"
            and obj.total_area and obj.total_area not in ("0", "0.0")
            and obj.floor
        )
