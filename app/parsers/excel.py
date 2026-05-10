"""Parser for Excel (.xlsx, .xls) and CSV files.

Uses pandas for reading with auto-detection of delimiters.
Column mapping is configured via admin panel (mapping_config.fields).
Supports: header row skip, blank row filtering, merged cell handling.
"""

import io
import logging
from typing import Optional

import chardet
import pandas as pd
from app.parsers.base import BaseParser, RawObject

logger = logging.getLogger(__name__)


class ExcelParser(BaseParser):
    """Parse Excel/CSV files with configurable column mapping."""

    def parse(self, content: bytes) -> list[RawObject]:
        results: list[RawObject] = []
        mapping = self.source_config.get("mapping_config") or {}
        field_mappings: dict = mapping.get("fields", {})
        header_row: int = mapping.get("header_row", 0)
        sheet_name = mapping.get("sheet_name", 0)

        if not field_mappings:
            self._log_error("No column mappings configured for Excel source")
            return results

        df = self._read_dataframe(content, header_row, sheet_name)
        if df is None or df.empty:
            self._log_error("Empty or unreadable file")
            return results

        # Normalize column names for matching
        df.columns = [str(c).strip().lower() for c in df.columns]
        norm_field_map = {k.strip().lower(): v for k, v in field_mappings.items()}

        for idx, row in df.iterrows():
            try:
                obj = self._parse_row(row, norm_field_map)
                if obj:
                    results.append(obj)
            except Exception as e:
                self._log_error(f"Error parsing row {idx}: {e}")

        logger.info(f"[{self.source_name}] Excel parser: {len(results)} objects from {len(df)} rows")
        return results

    def _read_dataframe(self, content: bytes, header_row: int,
                        sheet_name) -> Optional[pd.DataFrame]:
        """Try to read content as Excel or CSV."""

        # Try Excel first (.xlsx / .xls)
        try:
            return pd.read_excel(
                io.BytesIO(content),
                header=header_row,
                sheet_name=sheet_name,
                dtype=str,
            )
        except Exception:
            pass

        # Try CSV with encoding detection
        try:
            detected = chardet.detect(content[:10000])
            encoding = detected.get("encoding", "utf-8")

            # Try different delimiters
            for sep in [",", ";", "\t", "|"]:
                try:
                    df = pd.read_csv(
                        io.BytesIO(content),
                        header=header_row,
                        sep=sep,
                        encoding=encoding,
                        dtype=str,
                    )
                    if len(df.columns) > 1:
                        return df
                except Exception:
                    continue
        except Exception as e:
            self._log_error(f"Failed to read as CSV: {e}")

        return None

    def _parse_row(self, row: pd.Series, field_mappings: dict) -> Optional[RawObject]:
        """Parse a single DataFrame row using column mappings."""
        obj = RawObject()
        obj.developer_name = self.source_config.get("developer_name", "")

        has_data = False
        for source_col, target_field in field_mappings.items():
            if source_col not in row.index:
                continue

            value = str(row[source_col]).strip() if pd.notna(row.get(source_col)) else ""
            if not value or value == "nan":
                continue

            has_data = True

            if target_field == "photos":
                # Photos can be comma/semicolon separated URLs
                urls = [u.strip() for u in value.replace(";", ",").split(",") if u.strip()]
                obj.photos = urls
            elif hasattr(obj, target_field):
                setattr(obj, target_field, value)
            else:
                self._log_error(f"Unknown target field: {target_field}")

        if not has_data:
            return None

        # Ensure minimum required fields
        if not obj.flat_number and obj.source_object_id:
            obj.flat_number = obj.source_object_id

        return obj if (obj.flat_number and obj.price) else None
