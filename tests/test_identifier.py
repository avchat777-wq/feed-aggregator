"""Tests for the identification engine — ExternalId generation and code transliteration."""

import pytest
from app.identifier.identifier import IdentificationEngine


class TestMakeCode:
    """Test the Cyrillic transliteration used in ExternalId generation."""

    def test_simple_cyrillic(self):
        code = IdentificationEngine._make_code("СтройИнвест")
        assert code == "STROYINVEST"

    def test_with_spaces(self):
        code = IdentificationEngine._make_code("ЖК Солнечный")
        assert code == "ZHK-SOLNECHNYY"

    def test_with_quotes(self):
        # Quotes should be stripped (not alnum)
        code = IdentificationEngine._make_code('ЖК "Солнечный"')
        assert "SOLNECHNY" in code

    def test_latin(self):
        code = IdentificationEngine._make_code("River Park")
        assert code == "RIVER-PARK"

    def test_mixed(self):
        code = IdentificationEngine._make_code("ООО Строй22")
        assert "STROY22" in code

    def test_max_length(self):
        long_name = "А" * 100
        code = IdentificationEngine._make_code(long_name)
        assert len(code) <= 30

    def test_empty(self):
        code = IdentificationEngine._make_code("")
        assert code == ""

    def test_special_chars(self):
        code = IdentificationEngine._make_code("Корпус-2/литер А")
        assert "-" in code
        assert "KORPUS" in code

    def test_yo_letter(self):
        code = IdentificationEngine._make_code("Берёзка")
        assert "BEREZKA" in code

    def test_shcha(self):
        code = IdentificationEngine._make_code("Площадь")
        assert "PLOSCH" in code


class TestExternalIdFormat:
    """Verify ExternalId structure follows {DEV_CODE}-{JK_CODE}-{SEQ}."""

    def test_format_pattern(self):
        """External ID should have the form CODE-CODE-NNNNN."""
        import re
        dev_code = IdentificationEngine._make_code("СтройИнвест")
        jk_code = IdentificationEngine._make_code("Солнечный")
        # Simulate format
        ext_id = f"{dev_code}-{jk_code}-00001"
        assert re.match(r"^[A-Z0-9-]+-[A-Z0-9-]+-\d{5}$", ext_id)

    def test_code_deterministic(self):
        """Same input should always produce same code."""
        code1 = IdentificationEngine._make_code("ЖК Прибрежный")
        code2 = IdentificationEngine._make_code("ЖК Прибрежный")
        assert code1 == code2
