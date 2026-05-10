"""Parser for custom/arbitrary XML feed formats.

Uses configurable XPath mappings defined in admin panel.
The mapping_config from source contains:
  - item_xpath: XPath to find each object element
  - fields: dict of { target_field: xpath_expression }
"""

import logging
from lxml import etree
from app.parsers.base import BaseParser, RawObject

logger = logging.getLogger(__name__)


class CustomXmlParser(BaseParser):
    """Parse arbitrary XML using XPath-based mapping configuration."""

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []
        mapping = self.source_config.get("mapping_config") or {}

        item_xpath = mapping.get("item_xpath", "//item")
        field_mappings: dict = mapping.get("fields", {})

        if not field_mappings:
            self._log_error("No field mappings configured for custom XML source")
            return results

        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            self._log_error(f"Invalid XML: {e}")
            return results

        items = root.xpath(item_xpath)
        if not items:
            self._log_error(f"No items found at XPath: {item_xpath}")
            return results

        for item in items:
            try:
                obj = self._parse_item(item, field_mappings)
                if obj:
                    results.append(obj)
            except Exception as e:
                self._log_error(f"Error parsing custom XML item: {e}")

        logger.info(f"[{self.source_name}] Custom XML parser: {len(results)} objects parsed")
        return results

    def _parse_item(self, item, field_mappings: dict) -> RawObject:
        """Parse a single item using XPath field mappings."""
        obj = RawObject()
        obj.developer_name = self.source_config.get("developer_name", "")

        for target_field, xpath_expr in field_mappings.items():
            try:
                # XPath may return elements or strings
                result = item.xpath(xpath_expr)
                if not result:
                    continue

                if isinstance(result[0], str):
                    value = result[0].strip()
                elif hasattr(result[0], "text"):
                    value = (result[0].text or "").strip()
                else:
                    value = str(result[0]).strip()

                if not value:
                    continue

                # Handle special fields
                if target_field == "photos":
                    # Collect all photo URLs
                    photos = []
                    for r in result:
                        if isinstance(r, str):
                            photos.append(r.strip())
                        elif hasattr(r, "text") and r.text:
                            photos.append(r.text.strip())
                    obj.photos = photos
                elif hasattr(obj, target_field):
                    setattr(obj, target_field, value)
                else:
                    self._log_error(f"Unknown target field: {target_field}")

            except etree.XPathError as e:
                self._log_error(f"Invalid XPath '{xpath_expr}' for field '{target_field}': {e}")

        return obj if obj.flat_number or obj.source_object_id else None
