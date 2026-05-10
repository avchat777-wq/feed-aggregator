"""Parser for CIAN Feed v2 XML format.

Structure: <Feed> -> <Feed_Version>2</Feed_Version> -> <Object> elements.
Key fields: ExternalId, Category (newBuildingFlatSale), JKSchema (Id, House, Flat),
FlatRoomsCount, TotalArea, FloorNumber, BargainTerms (Price, SaleType),
Decoration, Photos, Phones.
"""

import logging
from lxml import etree
from app.parsers.base import BaseParser, RawObject

logger = logging.getLogger(__name__)


class CianParser(BaseParser):
    """Parse CIAN Feed v2 XML."""

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            self._log_error(f"Invalid XML: {e}")
            return results

        objects = root.findall(".//Object") or root.findall(".//object")

        for obj_el in objects:
            try:
                obj = self._parse_object(obj_el)
                if obj and obj.price and obj.jk_name:
                    results.append(obj)
                else:
                    ext_id = self._text(obj_el, "ExternalId")
                    self._log_error(f"Skipped CIAN Object {ext_id}: missing required fields")
            except Exception as e:
                self._log_error(f"Error parsing CIAN Object: {e}")

        logger.info(f"[{self.source_name}] CIAN parser: {len(results)} objects parsed")
        return results

    @staticmethod
    def _text(parent, tag: str) -> str:
        el = parent.find(tag)
        return (el.text or "").strip() if el is not None else ""

    def _parse_object(self, obj_el) -> RawObject:
        t = lambda tag: self._text(obj_el, tag)

        obj = RawObject()
        obj.source_object_id = t("ExternalId") or t("Id")
        obj.rooms = t("FlatRoomsCount")
        obj.total_area = t("TotalArea")
        obj.living_area = t("LivingArea") or None
        obj.kitchen_area = t("KitchenArea") or None
        obj.floor = t("FloorNumber")
        obj.floors_total = t("FloorsCount") or None
        obj.decoration = t("Decoration") or None
        obj.description = t("Description")

        # JKSchema — residential complex hierarchy
        jk = obj_el.find("JKSchema")
        if jk is not None:
            jk_id = self._text(jk, "Id")
            obj.jk_id_cian = jk_id or None
            obj.jk_name = self._text(jk, "n") or self._text(jk, "Name")

            house = jk.find("House")
            if house is not None:
                obj.house_name = self._text(house, "n") or self._text(house, "Name")

                flat = house.find("Flat")
                if flat is not None:
                    obj.flat_number = self._text(flat, "FlatNumber") or obj.source_object_id
                    obj.section_number = self._text(flat, "SectionNumber") or None
                else:
                    obj.flat_number = obj.source_object_id
            else:
                obj.flat_number = obj.source_object_id
        else:
            obj.jk_name = t("ResidentialComplexName") or t("JKName") or ""
            obj.flat_number = t("FlatNumber") or obj.source_object_id

        # BargainTerms — price and sale type
        bargain = obj_el.find("BargainTerms")
        if bargain is not None:
            obj.price = self._text(bargain, "Price")
            obj.sale_type = self._text(bargain, "SaleType") or None

        # Phones
        phones_el = obj_el.find("Phones")
        if phones_el is not None:
            for ps in phones_el.findall("PhoneSchema"):
                country = self._text(ps, "CountryCode")
                number = self._text(ps, "Number")
                if number:
                    obj.phone = f"{country}{number}".replace("+", "")
                    break

        # Photos
        photos_el = obj_el.find("Photos")
        if photos_el is not None:
            for photo in photos_el.findall("PhotoSchema"):
                url = self._text(photo, "FullUrl") or self._text(photo, "Url")
                if url:
                    obj.photos.append(url)
        # Also try <Photo> direct children
        for photo in obj_el.findall("Photo"):
            url = photo.text or photo.get("url", "")
            if url.strip():
                obj.photos.append(url.strip())

        obj.developer_name = (
            t("DeveloperName") or
            self.source_config.get("developer_name", "")
        )

        return obj
