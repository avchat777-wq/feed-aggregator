"""Parser for Avito Autoload XML feed format.

Structure: <Ads> -> <Ad> elements.
Supports avito (formatVersion=3) and avito_builder formats from macroserver.ru.

Key differences from other formats:
- JK name is often NOT in the feed (no <NewDevelopmentName> tag).
  Resolved via Avito New Developments directory (avito_lookup service).
  Fallback: mapping_config = {"jk_name": "..."} in source settings.
- Non-apartment ads (garages, parking) are filtered out automatically.
- <NewDevelopmentId> is used for JK lookup and stored as jk_id_cian.
"""

import logging
from lxml import etree
from app.parsers.base import BaseParser, RawObject
from app.services.avito_lookup import avito_lookup

logger = logging.getLogger(__name__)

# Categories that are apartments/new buildings
APARTMENT_CATEGORIES = {
    "квартиры", "квартира",
    "новостройки", "новостройка",
}

# Parking / storage — include with proper object_type
PARKING_CATEGORIES = {
    "гаражи и машиноместа", "гараж", "машиноместо", "паркинг",
}

# Categories to explicitly skip (commercial, land, rooms, etc.)
SKIP_CATEGORIES = {
    "коммерческая недвижимость", "офис",
    "земельные участки", "дома, дачи, коттеджи",
    "комнаты",
}

# Category → object_type for Intrum
CATEGORY_TYPE_MAP = {
    "квартиры": "квартира",
    "квартира": "квартира",
    "новостройки": "квартира",
    "новостройка": "квартира",
    "гаражи и машиноместа": "машиноместо",
    "гараж": "машиноместо",
    "машиноместо": "машиноместо",
    "паркинг": "машиноместо",
    "кладовка": "кладовка",
    "кладовки": "кладовка",
    "апартаменты": "апартаменты",
}


class AvitoParser(BaseParser):
    """Parse Avito Autoload XML feed (formatVersion 3)."""

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            self._log_error(f"Invalid XML: {e}")
            return results

        ads = root.findall(".//Ad") or root.findall(".//ad")

        skipped_category = 0
        for ad in ads:
            try:
                # Filter by category
                category = self._text(ad, "Category").lower().strip()
                if category in SKIP_CATEGORIES:
                    skipped_category += 1
                    continue
                if category and category not in APARTMENT_CATEGORIES and category not in PARKING_CATEGORIES:
                    # Unknown category — allow through but log
                    logger.debug(f"[{self.source_name}] Unknown category: {category!r}")

                obj_type = CATEGORY_TYPE_MAP.get(category, "квартира")
                obj = self._parse_ad(ad, object_type=obj_type)
                if obj and obj.price and obj.price != "0":
                    results.append(obj)
                else:
                    self._log_error(
                        f"Skipped Ad {self._text(ad, 'Id')}: no price"
                    )
            except Exception as e:
                self._log_error(f"Error parsing Ad: {e}")

        if skipped_category:
            logger.info(
                f"[{self.source_name}] Skipped {skipped_category} non-apartment ads"
            )

        logger.info(f"[{self.source_name}] Avito parser: {len(results)} objects parsed")
        return results

    @staticmethod
    def _text(parent, tag: str) -> str:
        el = parent.find(tag)
        return (el.text or "").strip() if el is not None else ""

    def _parse_ad(self, ad, object_type: str = "квартира") -> RawObject:
        t = lambda tag: self._text(ad, tag)

        obj = RawObject()
        obj.source_object_id = t("Id")
        obj.object_type = object_type

        # CIAN/Avito JK ID from <NewDevelopmentId>
        dev_id = t("NewDevelopmentId") or None
        obj.jk_id_cian = dev_id

        # JK name resolution priority:
        # 1. Direct tag in feed (rare)
        # 2. Avito New Developments directory lookup by NewDevelopmentId
        # 3. mapping_config.jk_name set by admin in source settings
        _mc = self.source_config.get("mapping_config") or {}
        _mapping_jk = _mc.get("jk_name", "") if isinstance(_mc, dict) else ""

        feed_jk = (
            t("NewDevelopmentName") or
            t("ResidentialComplex") or
            t("ComplexName") or
            t("ObjectName") or
            t("BuildingName") or
            t("HousingComplex") or
            t("JKName") or
            t("jk_name")
        )

        # Try Avito directory lookup
        lookup_info = avito_lookup.get(dev_id) if dev_id else None

        if feed_jk:
            obj.jk_name = feed_jk
        elif lookup_info:
            obj.jk_name = lookup_info.jk_name
            # Fill house_name from Housing entry if not already in feed
            if lookup_info.house_name and not (t("HouseName") or t("Building") or t("Corpus")):
                obj.house_name = lookup_info.house_name
            # Fill address from lookup if not in feed
            if lookup_info.address and not (t("Address") or t("Location")):
                obj.address = lookup_info.address
        else:
            obj.jk_name = _mapping_jk

        obj.flat_number = (
            t("ApartmentNumber") or t("FlatNumber") or
            t("Flat") or obj.source_object_id
        )
        obj.floor = t("Floor") or t("FloorNumber") or "0"
        obj.floors_total = t("Floors") or t("FloorsCount") or None
        obj.rooms = t("Rooms") or t("RoomsCount") or "0"
        obj.total_area = t("Square") or t("TotalArea") or t("Area") or "0"
        obj.living_area = t("LivingSquare") or t("LivingArea") or None
        obj.kitchen_area = t("KitchenSquare") or t("KitchenArea") or None
        obj.price = t("Price") or t("Cost") or "0"

        # Address: feed value takes priority over lookup
        if not obj.address:
            obj.address = t("Address") or t("Location") or None
            if not obj.address and lookup_info and lookup_info.address:
                obj.address = lookup_info.address

        obj.decoration = t("Decoration") or t("Renovation") or t("Finish") or None
        obj.sale_type = t("DealType") or t("SaleType") or None
        if not obj.house_name:
            obj.house_name = t("HouseName") or t("Building") or t("Corpus") or None
        obj.section_number = t("Section") or t("SectionNumber") or None
        obj.description = t("Description") or None
        obj.phone = (
            t("ContactPhone") or t("Phone") or
            self.source_config.get("phone_override", "")
        )
        obj.developer_name = (
            self.source_config.get("developer_name", "") or
            t("CompanyName") or t("ManagerName")
        )

        # Photos: <Images><Image url="..."/></Images>
        for container_tag in ("Images", "images", "Photos", "photos"):
            container = ad.find(container_tag)
            if container is not None:
                for child in container:
                    url = child.get("url", "") or child.get("src", "") or (child.text or "")
                    if url.strip().startswith("http"):
                        obj.photos.append(url.strip())
                if obj.photos:
                    break

        # Fallback: numbered image tags
        if not obj.photos:
            for i in range(1, 20):
                url = t(f"ImageUrl{i}") or t(f"Photo{i}") or t(f"Image{i}")
                if url.startswith("http"):
                    obj.photos.append(url)

        return obj
