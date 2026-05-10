"""Tests for DomClickParser — covers all platform variants."""

import sys
import types

# ── Minimal stubs so we can import parser without DB / config ────────────────
for mod in ("app.config", "app.database"):
    stub = types.ModuleType(mod)
    sys.modules[mod] = stub

import pytest
from app.parsers.domclick import DomClickParser


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_parser(developer_name="ООО Тест"):
    return DomClickParser({"name": "test", "developer_name": developer_name})


def xml(body: str) -> bytes:
    return f'<?xml version="1.0" encoding="utf-8"?>\n{body}'.encode("utf-8")


# ── Test 1: Standard DomClick feed (<feed><object>) ───────────────────────────

STANDARD_FEED = xml("""
<feed>
  <object>
    <id>101</id>
    <type>Flat</type>
    <status>active</status>
    <newbuilding>ЖК Ёлочки</newbuilding>
    <newbuilding_id>5001</newbuilding_id>
    <house>Корпус 1</house>
    <section>3</section>
    <flat_number>75</flat_number>
    <floor>5</floor>
    <floors_count>12</floors_count>
    <rooms_count>2</rooms_count>
    <area>52.3</area>
    <living_area>30.5</living_area>
    <kitchen_area>8.2</kitchen_area>
    <price>4500000</price>
    <sale_type>DDU</sale_type>
    <finish_type>WhiteBox</finish_type>
    <phones><phone>+79138765432</phone></phones>
    <description>Просторная квартира</description>
    <images>
      <image>https://example.com/photo1.jpg</image>
      <image>https://example.com/photo2.jpg</image>
    </images>
  </object>
</feed>
""")


def test_standard_feed_basic_fields():
    parser = make_parser("Жилищная Инициатива")
    objs = parser.parse(STANDARD_FEED)
    assert len(objs) == 1
    obj = objs[0]
    assert obj.source_object_id == "101"
    assert obj.jk_name == "ЖК Ёлочки"
    assert obj.jk_id_cian == "5001"
    assert obj.house_name == "Корпус 1"
    assert obj.section_number == "3"
    assert obj.flat_number == "75"
    assert obj.floor == "5"
    assert obj.floors_total == "12"
    assert obj.rooms == "2"
    assert obj.total_area == "52.3"
    assert obj.living_area == "30.5"
    assert obj.kitchen_area == "8.2"
    assert obj.price == "4500000"
    assert obj.sale_type == "DDU"
    assert obj.decoration == "rough"   # WhiteBox -> rough
    assert obj.phone == "+79138765432"
    assert obj.description == "Просторная квартира"
    assert len(obj.photos) == 2
    assert obj.status == "active"
    assert obj.developer_name == "Жилищная Инициатива"


# ── Test 2: <objects><object> root variant ────────────────────────────────────

OBJECTS_ROOT_FEED = xml("""
<objects>
  <object>
    <id>202</id>
    <ComplexName>ЖК Сокол</ComplexName>
    <Floor>7</Floor>
    <FloorsCount>18</FloorsCount>
    <Rooms>1</Rooms>
    <Square>38.5</Square>
    <Price>3200000</Price>
    <phone>+79001234567</phone>
  </object>
</objects>
""")


def test_objects_root_variant():
    """Domoplaner / custom variant with <objects> root and capitalised tags."""
    parser = make_parser("Алгоритм")
    objs = parser.parse(OBJECTS_ROOT_FEED)
    assert len(objs) == 1
    obj = objs[0]
    assert obj.jk_name == "ЖК Сокол"
    assert obj.floor == "7"
    assert obj.floors_total == "18"
    assert obj.rooms == "1"
    assert obj.total_area == "38.5"
    assert obj.price == "3200000"


# ── Test 3: Multi-JK feed (one URL, many complexes) ──────────────────────────

MULTI_JK_FEED = xml("""
<feed>
  <object>
    <id>1</id>
    <newbuilding>ЖК Смарт</newbuilding>
    <flat_number>10</flat_number>
    <floor>3</floor>
    <rooms_count>1</rooms_count>
    <area>35.0</area>
    <price>2900000</price>
    <phones><phone>79001111111</phone></phones>
  </object>
  <object>
    <id>2</id>
    <newbuilding>ЖК Титул</newbuilding>
    <flat_number>55</flat_number>
    <floor>10</floor>
    <rooms_count>3</rooms_count>
    <area>85.0</area>
    <price>7500000</price>
    <phones><phone>79001111111</phone></phones>
  </object>
</feed>
""")


def test_multi_jk_feed_returns_all_objects():
    """All objects from a multi-JK feed should be parsed."""
    parser = make_parser("Т-Строй")
    objs = parser.parse(MULTI_JK_FEED)
    assert len(objs) == 2
    jk_names = {o.jk_name for o in objs}
    assert "ЖК Смарт" in jk_names
    assert "ЖК Титул" in jk_names


def test_multi_jk_feed_preserves_jk_names():
    parser = make_parser()
    objs = parser.parse(MULTI_JK_FEED)
    smart = next(o for o in objs if o.jk_name == "ЖК Смарт")
    titul = next(o for o in objs if o.jk_name == "ЖК Титул")
    assert smart.flat_number == "10"
    assert titul.rooms == "3"


# ── Test 4: Status mapping ────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("active",       "active"),
    ("Active",       "active"),
    ("1",            "active"),
    ("В продаже",    "active"),  # lower: "в продаже"
    ("free",         "active"),
    ("booked",       "booked"),
    ("reserved",     "booked"),
    ("sold",         "sold"),
    ("Продано",      "sold"),    # lower: "продано"
    ("unknown_val",  "active"),  # unknown defaults to active
    ("",             "active"),
])
def test_status_mapping(raw, expected):
    from app.parsers.domclick import DomClickParser as P
    assert P._map_status(raw) == expected


# ── Test 5: Finish type (decoration) mapping ──────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("WhiteBox",        "rough"),
    ("Whitebox",        "rough"),
    ("WithoutFinish",   "without"),
    ("Clean",           "fine"),
    ("Turnkey",         "turnkey"),
    ("turnkey",         "turnkey"),
    ("черновая",        "черновая"),   # not in DomClick map → returned as-is
    ("",                None),
])
def test_decoration_mapping(raw, expected):
    from app.parsers.domclick import DomClickParser as P
    assert P._map_decoration(raw) == expected


# ── Test 6: Photo extraction ──────────────────────────────────────────────────

PHOTO_FEED = xml("""
<feed>
  <object>
    <id>301</id>
    <newbuilding>ЖК Тест</newbuilding>
    <floor>2</floor>
    <rooms_count>1</rooms_count>
    <area>32.0</area>
    <price>2500000</price>
    <phones><phone>79000000000</phone></phones>
    <images>
      <image>https://img.example.com/1.jpg</image>
      <image>https://img.example.com/2.jpg</image>
      <image>https://img.example.com/1.jpg</image>  <!-- duplicate -->
    </images>
  </object>
</feed>
""")


def test_photo_deduplication():
    """Duplicate photo URLs must be removed."""
    parser = make_parser()
    objs = parser.parse(PHOTO_FEED)
    assert len(objs) == 1
    # 3 listed, 1 duplicate → 2 unique
    assert len(objs[0].photos) == 2


# ── Test 7: Studio rooms ──────────────────────────────────────────────────────

STUDIO_FEED = xml("""
<feed>
  <object>
    <id>401</id>
    <newbuilding>ЖК Студио</newbuilding>
    <floor>4</floor>
    <rooms_count>Studio</rooms_count>
    <area>28.5</area>
    <price>1900000</price>
    <phones><phone>79000000001</phone></phones>
  </object>
</feed>
""")


def test_studio_rooms_normalized():
    parser = make_parser()
    objs = parser.parse(STUDIO_FEED)
    assert len(objs) == 1
    assert objs[0].rooms == "0"


# ── Test 8: Skip objects without price / area ─────────────────────────────────

INVALID_OBJECTS_FEED = xml("""
<feed>
  <object>
    <id>501</id>
    <newbuilding>ЖК Тест</newbuilding>
    <floor>3</floor>
    <rooms_count>2</rooms_count>
    <area>45.0</area>
    <price></price>
    <phones><phone>79000000002</phone></phones>
  </object>
  <object>
    <id>502</id>
    <newbuilding>ЖК Тест</newbuilding>
    <floor>5</floor>
    <rooms_count>1</rooms_count>
    <area></area>
    <price>3000000</price>
    <phones><phone>79000000002</phone></phones>
  </object>
  <object>
    <id>503</id>
    <newbuilding>ЖК Тест</newbuilding>
    <floor>7</floor>
    <rooms_count>3</rooms_count>
    <area>70.0</area>
    <price>6000000</price>
    <phones><phone>79000000002</phone></phones>
  </object>
</feed>
""")


def test_invalid_objects_skipped():
    """Objects without price or area must be skipped; valid ones kept."""
    parser = make_parser()
    objs = parser.parse(INVALID_OBJECTS_FEED)
    assert len(objs) == 1
    assert objs[0].source_object_id == "503"


# ── Test 9: Invalid XML ───────────────────────────────────────────────────────

def test_invalid_xml_returns_empty():
    parser = make_parser()
    objs = parser.parse(b"this is not xml at all <><>")
    assert objs == []
    assert len(parser.errors) > 0


# ── Test 10: Parser registry includes domclick types ─────────────────────────

def test_registry_contains_domclick_types():
    # Re-stub app.config / app.database before importing parsers __init__
    from app.parsers import PARSER_REGISTRY, get_parser
    assert "domclick"     in PARSER_REGISTRY
    assert "domclick_pro" in PARSER_REGISTRY
    assert "avito_builder" in PARSER_REGISTRY
    # domclick and domclick_pro both resolve to DomClickParser
    assert get_parser("domclick") is DomClickParser
    assert get_parser("domclick_pro") is DomClickParser


# ── Test 11: Profitbase DomClick variant (alternative tag names) ──────────────

PROFITBASE_FEED = xml("""
<feed>
  <object>
    <id>pb-1001</id>
    <complex_name>ЖК Новая История</complex_name>
    <building_name>Литер А</building_name>
    <ApartmentNumber>23</ApartmentNumber>
    <FloorNumber>4</FloorNumber>
    <TotalFloors>9</TotalFloors>
    <RoomsCount>2</RoomsCount>
    <TotalArea>58.7</TotalArea>
    <Price>5100000</Price>
    <SaleType>DDU</SaleType>
    <Decoration>Черновая</Decoration>
    <phones>
      <phone>+79139000000</phone>
    </phones>
    <images>
      <image>https://profitbase.ru/img/apt1.jpg</image>
    </images>
  </object>
</feed>
""")


def test_profitbase_variant():
    """Profitbase uses alternative capitalisation for many field names."""
    parser = make_parser("Адалин-Строй")
    objs = parser.parse(PROFITBASE_FEED)
    assert len(objs) == 1
    obj = objs[0]
    assert obj.source_object_id == "pb-1001"
    assert obj.jk_name == "ЖК Новая История"
    assert obj.house_name == "Литер А"
    assert obj.flat_number == "23"
    assert obj.floor == "4"
    assert obj.floors_total == "9"
    assert obj.rooms == "2"
    assert obj.total_area == "58.7"
    assert obj.price == "5100000"
    assert obj.sale_type == "DDU"
    assert len(obj.photos) == 1
