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

        # JK name — try all known Avito/macroserver field names
        _mc = self.source_config.get("mapping_config") or {}
        _mapping_jk = _mc.get("jk_name", "") if isinstance(_mc, dict) else ""
        obj.jk_name = (
            t("NewDevelopmentName") or
            t("ResidentialComplex") or
            t("ComplexName") or
            t("ObjectName") or
            t("BuildingName") or
            t("HousingComplex") or
            t("JKName") or
            t("jk_name") or
            t("Title") or
            _mapping_jk
        )

        obj.flat_number = t("FlatNumber") or t("ApartmentNumber") or t("Flat") or obj.source_object_id
        obj.floor = t("Floor") or t("FloorNumber") or "0"
        obj.floors_total = t("Floors") or t("FloorsCount") or t("FloorsTotal") or None
        obj.rooms = t("Rooms") or t("RoomsCount") or t("RoomCount") or "0"
        obj.total_area = t("Square") or t("TotalArea") or t("Area") or "0"
        obj.living_area = t("LivingSquare") or t("LivingArea") or None
        obj.kitchen_area = t("KitchenSquare") or t("KitchenArea") or None
        obj.price = t("Price") or t("Cost") or "0"
        obj.description = t("Description") or t("Text") or None
        obj.address = t("Address") or t("Location") or None
        obj.decoration = t("Decoration") or t("Renovation") or t("Finish") or None
        obj.sale_type = t("DealType") or t("SaleType") or None
        obj.house_name = t("HouseName") or t("Building") or t("Corpus") or t("Liter") or None
        obj.section_number = t("Section") or t("SectionNumber") or None
        obj.phone = (
            t("ContactPhone") or t("Phone") or
            self.source_config.get("phone_override", "")
        )

        # Photos — try <Images><Image url="...">, <Photos><Photo>, direct <ImageUrl>
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

        obj.developer_name = self.source_config.get("developer_name", "")

        return obj
