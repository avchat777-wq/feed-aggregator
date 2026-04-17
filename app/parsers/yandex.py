"""Parser for Yandex.Realty (YRL) XML feed format.

Structure: <realty-feed> -> <offer> elements.
Key fields: offer@id, type, category, location (address, lat, lon),
sales-agent (phone, name), price (value, currency), area (value),
rooms, floor, building-name, description, image.
"""

import logging
from lxml import etree
from app.parsers.base import BaseParser, RawObject

logger = logging.getLogger(__name__)


class YandexParser(BaseParser):
    """Parse Yandex.Realty feed (YRL format)."""

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            self._log_error(f"Invalid XML: {e}")
            return results

        # Handle namespace if present
        ns = root.nsmap.get(None, "")
        prefix = f"{{{ns}}}" if ns else ""

        offers = root.findall(f".//{prefix}offer")
        if not offers:
            # Try without namespace
            offers = root.findall(".//offer")

        for offer in offers:
            try:
                obj = self._parse_offer(offer, prefix)
                if obj and obj.flat_number and obj.price:
                    results.append(obj)
                else:
                    self._log_error(
                        f"Skipped offer {offer.get('internal-id', '?')}: missing required fields"
                    )
            except Exception as e:
                self._log_error(f"Error parsing offer: {e}")

        logger.info(f"[{self.source_name}] Yandex parser: {len(results)} objects parsed")
        return results

    def _parse_offer(self, offer, prefix: str) -> RawObject:
        """Parse a single <offer> element."""

        def find_el(tag: str, parent=None):
            ctx = parent if parent is not None else offer
            el = ctx.find(f"{prefix}{tag}")
            if el is None:
                el = ctx.find(tag)
            return el

        def text(tag: str, parent=None) -> str:
            el = find_el(tag, parent)
            return (el.text or "").strip() if el is not None else ""

        def nested_text(parent_tag: str, child_tag: str) -> str:
            parent_el = find_el(parent_tag)
            if parent_el is not None:
                return text(child_tag, parent_el)
            return ""

        obj = RawObject()
        obj.source_object_id = offer.get("internal-id", "") or offer.get("id", "")
        obj.jk_name = text("building-name") or text("yandex-building-name")
        obj.flat_number = text("apartment") or text("flat-number") or obj.source_object_id
        obj.floor = text("floor")
        obj.floors_total = text("floors-total") or text("floors-offered") or None
        obj.rooms = text("rooms") or text("rooms-offered")
        obj.total_area = nested_text("area", "value") or text("area")
        obj.living_area = nested_text("living-space", "value") or text("living-space") or None
        obj.kitchen_area = nested_text("kitchen-space", "value") or text("kitchen-space") or None
        obj.price = nested_text("price", "value") or text("price")
        obj.description = text("description")
        obj.decoration = text("renovation") or text("decoration") or None
        obj.sale_type = text("deal-status") or None

        # Location
        location = find_el("location")
        if location is not None:
            obj.address = text("address", location)
            obj.latitude = text("latitude", location) or None
            obj.longitude = text("longitude", location) or None

        # Phone
        agent = find_el("sales-agent")
        if agent is not None:
            obj.phone = text("phone", agent)

        # Photos (deduplicate between prefixed and non-prefixed search)
        seen_urls = set()
        for img in offer.findall(f"{prefix}image") + offer.findall("image"):
            if img.text and img.text.strip():
                url = img.text.strip()
                if url not in seen_urls:
                    obj.photos.append(url)
                    seen_urls.add(url)

        # Developer name from source config
        obj.developer_name = self.source_config.get("developer_name", "")

        return obj
