"""Feed generator — produces unified XML feed for CRM Intrum.

Per ТЗ section 9 and 16:
- Format: XML UTF-8, CIAN Feed v2 structure
- Only objects with status='active'
- Atomic write: generate to temp file, then rename
- Auto-split if > 20 MB
- Name template: "{rooms}-к кв, {area} м², {JK}, этаж {floor}"
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.object import Object

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 20


class FeedGenerator:
    """Generates the unified XML feed file."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.output_dir = Path(settings.feed_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self) -> str:
        """Generate the XML feed and return the file path.

        Returns:
            Absolute path to the generated feed file.

        Raises:
            Exception if generation fails (caller should handle).
        """
        # Fetch all active objects
        stmt = select(Object).where(Object.status == "active").order_by(Object.external_id)
        result = await self.session.execute(stmt)
        objects = list(result.scalars().all())

        logger.info(f"Generating feed with {len(objects)} active objects")

        if not objects:
            logger.warning("No active objects to include in feed")

        # Build XML
        xml_bytes = self._build_xml(objects)
        size_mb = len(xml_bytes) / (1024 * 1024)

        # Handle splitting if needed
        if size_mb > MAX_FILE_SIZE_MB and len(objects) > 100:
            return await self._generate_split(objects)

        # Atomic write
        feed_path = self.output_dir / "feed.xml"
        self._atomic_write(feed_path, xml_bytes)

        logger.info(f"Feed generated: {feed_path} ({size_mb:.1f} MB, {len(objects)} objects)")
        return str(feed_path)

    def _build_xml(self, objects: list[Object]) -> bytes:
        """Build complete XML document from objects."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        root = etree.Element("Feed")
        etree.SubElement(root, "Feed_Version").text = "2"
        etree.SubElement(root, "Generated").text = now
        etree.SubElement(root, "Source").text = "MIEL-Barnaul-FeedAggregator"
        etree.SubElement(root, "ObjectsCount").text = str(len(objects))

        for obj in objects:
            self._add_object_element(root, obj)

        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )

    def _add_object_element(self, root, obj: Object):
        """Add a single <Object> element to the XML tree."""
        obj_el = etree.SubElement(root, "Object")

        etree.SubElement(obj_el, "ExternalId").text = obj.external_id
        etree.SubElement(obj_el, "Category").text = "newBuildingFlatSale"
        etree.SubElement(obj_el, "DeveloperName").text = obj.developer_name

        # JKSchema
        jk = etree.SubElement(obj_el, "JKSchema")
        if obj.jk_id_cian:
            etree.SubElement(jk, "Id").text = str(obj.jk_id_cian)
        etree.SubElement(jk, "n").text = obj.jk_name

        if obj.house_name:
            house = etree.SubElement(jk, "House")
            etree.SubElement(house, "n").text = obj.house_name
            flat = etree.SubElement(house, "Flat")
            etree.SubElement(flat, "FlatNumber").text = str(obj.flat_number)
            if obj.section_number:
                etree.SubElement(flat, "SectionNumber").text = str(obj.section_number)

        # Name auto-generation
        rooms_str = "Студия" if obj.rooms == 0 else f"{obj.rooms}-к кв"
        name = f"{rooms_str}, {obj.total_area} м², {obj.jk_name}, этаж {obj.floor}"
        etree.SubElement(obj_el, "Name").text = name

        etree.SubElement(obj_el, "FlatRoomsCount").text = str(obj.rooms)
        etree.SubElement(obj_el, "TotalArea").text = str(obj.total_area)

        if obj.living_area:
            etree.SubElement(obj_el, "LivingArea").text = str(obj.living_area)
        if obj.kitchen_area:
            etree.SubElement(obj_el, "KitchenArea").text = str(obj.kitchen_area)

        etree.SubElement(obj_el, "FloorNumber").text = str(obj.floor)
        if obj.floors_total:
            etree.SubElement(obj_el, "FloorsCount").text = str(obj.floors_total)

        etree.SubElement(obj_el, "FlatNumber").text = str(obj.flat_number)

        if obj.house_name:
            etree.SubElement(obj_el, "Building").text = obj.house_name

        if obj.decoration:
            etree.SubElement(obj_el, "Decoration").text = obj.decoration

        if obj.description:
            etree.SubElement(obj_el, "Description").text = obj.description

        # Phones
        if obj.phone:
            phones = etree.SubElement(obj_el, "Phones")
            ps = etree.SubElement(phones, "PhoneSchema")
            etree.SubElement(ps, "CountryCode").text = "+7"
            etree.SubElement(ps, "Number").text = obj.phone[1:] if obj.phone.startswith("7") else obj.phone

        # BargainTerms
        bargain = etree.SubElement(obj_el, "BargainTerms")
        etree.SubElement(bargain, "Price").text = str(obj.price)
        if obj.sale_type:
            etree.SubElement(bargain, "SaleType").text = obj.sale_type

        # Photos
        if obj.photos:
            photos_el = etree.SubElement(obj_el, "Photos")
            for url in obj.photos:
                photo = etree.SubElement(photos_el, "PhotoSchema")
                etree.SubElement(photo, "FullUrl").text = url

    async def _generate_split(self, objects: list[Object]) -> str:
        """Split objects into multiple feed files if too large."""
        chunk_size = len(objects) // 2
        parts = [objects[i:i + chunk_size] for i in range(0, len(objects), chunk_size)]

        paths = []
        for idx, part in enumerate(parts):
            xml_bytes = self._build_xml(part)
            feed_path = self.output_dir / f"feed_part{idx + 1}.xml"
            self._atomic_write(feed_path, xml_bytes)
            paths.append(str(feed_path))

        # Also write a combined feed (always provide single endpoint)
        full_xml = self._build_xml(objects)
        main_path = self.output_dir / "feed.xml"
        self._atomic_write(main_path, full_xml)

        logger.info(f"Feed split into {len(parts)} parts + full feed")
        return str(main_path)

    @staticmethod
    def _atomic_write(path: Path, data: bytes):
        """Write data to file atomically using temp file + rename."""
        dir_path = path.parent
        fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
        try:
            os.write(fd, data)
            os.close(fd)
            os.replace(tmp_path, str(path))
            # Ensure nginx and other processes can read the file
            os.chmod(path, 0o644)
            os.chmod(dir_path, 0o755)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise