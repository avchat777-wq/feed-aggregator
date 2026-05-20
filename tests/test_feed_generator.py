from types import SimpleNamespace

from lxml import etree

from app.generator.feed_generator import FeedGenerator


def _obj(**overrides):
    base = {
        "external_id": "TEST-001",
        "object_type": "квартира",
        "developer_name": "Developer",
        "jk_id_cian": None,
        "jk_name": "ЖК Тест",
        "house_name": "",
        "flat_number": "42",
        "section_number": None,
        "rooms": 1,
        "total_area": 40.0,
        "living_area": None,
        "kitchen_area": None,
        "floor": 5,
        "floors_total": 16,
        "decoration": None,
        "address": None,
        "latitude": None,
        "longitude": None,
        "description": None,
        "phone": "73852533522",
        "price": 5_000_000,
        "sale_type": None,
        "photos": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _ad(obj):
    xml = FeedGenerator.__new__(FeedGenerator)._build_xml([obj])
    return etree.fromstring(xml).find("Ad")


def test_flat_number_is_nested_for_flat_without_house_name():
    ad = _ad(_obj(house_name="", flat_number="193"))

    assert ad.findtext("FlatNumber") == "193"
    assert ad.findtext("JKSchema/House/Flat/FlatNumber") == "193"
    assert ad.find("JKSchema/House/n") is None


def test_flat_number_is_not_exported_for_parking():
    ad = _ad(_obj(object_type="машиноместо", flat_number="P-1", rooms=0, floor=-1))

    assert ad.find("FlatNumber") is None
    assert ad.find("JKSchema/House/Flat/FlatNumber") is None
