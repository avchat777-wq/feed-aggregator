"""Parser for Avito Autoload XML feed format.

Structure: <Ads> -> <Ad> elements.
Key fields: Id, Category, OperationType, Address, Price, Rooms,
Square, Floor, Floors, HouseType, Description, Images/Image.
"""

import logging
from lxml import etree
from app.parsers.base import BaseParser, RawObject

logger = logging.getLogger(__name__)


class AvitoParser(BaseParser):
    """Parse Avito Autoload XML feed."""

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            self._log_error(f"Invalid XML: {e}")
            return results

        ads = root.findall(".//Ad")
        if not ads:
            ads = root.findall(".//ad")

        for ad in ads:
            try:
                obj = self._parse_ad(ad)
                if obj and obj.price:
                    results.append(obj)
                else:
                    self._log_error(f"Skipped Ad {self._text(ad, 'Id')}: missing required fields")
            except Exception as e:
                self._log_error(f"Error parsing Ad: {e}")

        logger.info(f"[{self.source_name}] Avito parser: {len(results)} objects parsed")
        return results

    @staticmethod
    def _text(parent, tag: str) -> str:
        el = parent.find(tag)
        return (el.text or "").strip() if el is not None else ""

    def _parse_ad(self, ad) -> RawObject:
        t = lambda tag: self._text(ad, tag)

        obj = RawObject()
        obj.source_object_id = t("Id")
        obj.jk_name = t("NewDevelopmentName") or t("ObjectName") or t("Title")
        obj.flat_number = t("FlatNumber") or t("ApartmentNumber") or obj.source_object_id
        obj.floor = t("Floor")
        obj.floors_total = t("Floors") or None
        obj.rooms = t("Rooms")
        obj.total_area = t("Square")
        obj.living_area = t("LivingSquare") or None
        obj.kitchen_area = t("KitchenSquare") or None
        obj.price = t("Price")
        obj.description = t("Description")
        obj.address = t("Address")
        obj.decoration = t("Decoration") or t("Renovation") or None
        obj.sale_type = t("DealType") or None
        obj.house_name = t("HouseName") or t("Building") or None
        obj.section_number = t("Section") or None
        obj.phone = t("ContactPhone") or t("Phone") or ""

        # Photos
        images = ad.find("Images")
        if images is not None:
            for img in images.findall("Image"):
                url = img.get("url", "") or (img.text or "")
                if url.strip():
                    obj.photos.append(url.strip())

        obj.developer_name = self.source_config.get("developer_name", "")

        return obj
