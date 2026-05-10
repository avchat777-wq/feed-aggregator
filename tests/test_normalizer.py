"""Tests for the normalization module."""

import pytest
from decimal import Decimal
from app.parsers.base import RawObject
from app.normalizer.normalizer import (
    normalize_object,
    _normalize_area,
    _normalize_price,
    _normalize_rooms,
    _normalize_phone,
    _normalize_decoration,
    _normalize_sale_type,
)


# ─────────────── Area normalization ───────────────

class TestNormalizeArea:
    def test_simple_number(self):
        assert _normalize_area("65.5") == Decimal("65.5")

    def test_comma_separator(self):
        assert _normalize_area("65,5") == Decimal("65.5")

    def test_with_units(self):
        assert _normalize_area("65.5 кв.м") == Decimal("65.5")

    def test_with_sqm_symbol(self):
        assert _normalize_area("65.5 м²") == Decimal("65.5")

    def test_empty(self):
        assert _normalize_area("") == Decimal("0")

    def test_none(self):
        assert _normalize_area(None) == Decimal("0")

    def test_rounding(self):
        assert _normalize_area("65.47") == Decimal("65.5")

    def test_integer(self):
        assert _normalize_area("65") == Decimal("65.0")


# ─────────────── Price normalization ───────────────

class TestNormalizePrice:
    def test_simple_integer(self):
        assert _normalize_price("5500000") == 5500000

    def test_with_spaces(self):
        assert _normalize_price("5 500 000") == 5500000

    def test_with_currency(self):
        assert _normalize_price("5500000 руб.") == 5500000

    def test_thousands(self):
        assert _normalize_price("5500 тыс. руб.") == 5500000

    def test_thousands_tr(self):
        assert _normalize_price("5500 т.р.") == 5500000

    def test_millions(self):
        assert _normalize_price("5.5 млн") == 5500000

    def test_empty(self):
        assert _normalize_price("") == 0

    def test_none(self):
        assert _normalize_price(None) == 0

    def test_with_comma(self):
        assert _normalize_price("5,5 млн") == 5500000


# ─────────────── Rooms normalization ───────────────

class TestNormalizeRooms:
    def test_studio_russian(self):
        assert _normalize_rooms("студия") == 0

    def test_studio_english(self):
        assert _normalize_rooms("studio") == 0

    def test_studio_short(self):
        assert _normalize_rooms("ст") == 0

    def test_free_layout(self):
        assert _normalize_rooms("свободная планировка") == 0

    def test_number(self):
        assert _normalize_rooms("2") == 2

    def test_number_with_text(self):
        assert _normalize_rooms("3-комн.") == 3

    def test_seven_plus(self):
        assert _normalize_rooms("7+") == 9

    def test_eight(self):
        assert _normalize_rooms("8") == 9

    def test_empty(self):
        assert _normalize_rooms("") == 0


# ─────────────── Phone normalization ───────────────

class TestNormalizePhone:
    def test_full_format_with_plus(self):
        assert _normalize_phone("+73852533522") == "73852533522"

    def test_eight_prefix(self):
        assert _normalize_phone("83852533522") == "73852533522"

    def test_ten_digits(self):
        assert _normalize_phone("3852533522") == "73852533522"

    def test_with_dashes(self):
        assert _normalize_phone("+7-385-253-3522") == "73852533522"

    def test_with_brackets(self):
        assert _normalize_phone("+7 (385) 253-35-22") == "73852533522"

    def test_with_spaces(self):
        assert _normalize_phone("7 385 253 35 22") == "73852533522"

    def test_empty(self):
        assert _normalize_phone("") == ""

    def test_none(self):
        assert _normalize_phone(None) == ""


# ─────────────── Decoration normalization ───────────────

class TestNormalizeDecoration:
    def test_without(self):
        assert _normalize_decoration("без отделки") == "without"

    def test_pre_finish(self):
        assert _normalize_decoration("предчистовая") == "without"

    def test_rough(self):
        assert _normalize_decoration("черновая") == "rough"

    def test_fine(self):
        assert _normalize_decoration("чистовая") == "fine"

    def test_white_box(self):
        assert _normalize_decoration("white box") == "fine"

    def test_turnkey(self):
        assert _normalize_decoration("под ключ") == "turnkey"

    def test_with_furniture(self):
        assert _normalize_decoration("с мебелью") == "turnkey"

    def test_english_passthrough(self):
        assert _normalize_decoration("fine") == "fine"

    def test_none(self):
        assert _normalize_decoration(None) is None

    def test_unknown(self):
        assert _normalize_decoration("какая-то другая") is None


# ─────────────── Sale type normalization ───────────────

class TestNormalizeSaleType:
    def test_ddu_russian(self):
        assert _normalize_sale_type("ДДУ") == "DDU"

    def test_214fz(self):
        assert _normalize_sale_type("214-ФЗ") == "DDU"

    def test_assignment_russian(self):
        assert _normalize_sale_type("переуступка") == "assignment"

    def test_cession(self):
        assert _normalize_sale_type("цессия") == "assignment"

    def test_pdkp(self):
        assert _normalize_sale_type("ПДКП") == "pdkp"

    def test_none(self):
        assert _normalize_sale_type(None) is None


# ─────────────── Full normalization ───────────────

class TestNormalizeObject:
    def test_full_normalization(self):
        raw = RawObject(
            source_object_id="TEST-001",
            developer_name="СтройИнвест",
            jk_name="ЖК Солнечный",
            flat_number="105",
            floor="7",
            floors_total="10",
            rooms="2",
            total_area="65,5 кв.м",
            living_area="35.2",
            kitchen_area="12.1",
            price="8 500 000 руб.",
            sale_type="ДДУ",
            decoration="чистовая",
            phone="+7 (385) 253-35-22",
            status="active",
            photos=["https://example.com/1.jpg", "invalid-url", "https://example.com/2.jpg"],
        )

        u = normalize_object(raw, source_id=1)

        assert u.source_id == 1
        assert u.source_object_id == "TEST-001"
        assert u.developer_name == "СтройИнвест"
        assert u.jk_name == "ЖК Солнечный"
        assert u.flat_number == "105"
        assert u.floor == 7
        assert u.floors_total == 10
        assert u.rooms == 2
        assert u.total_area == Decimal("65.5")
        assert u.living_area == Decimal("35.2")
        assert u.kitchen_area == Decimal("12.1")
        assert u.price == 8500000
        assert u.sale_type == "DDU"
        assert u.decoration == "fine"
        assert u.phone == "73852533522"
        assert u.status == "active"
        assert len(u.photos) == 2  # invalid-url filtered out
        assert u.price_per_sqm == int(8500000 / 65.5)
        assert u.hash  # non-empty hash

    def test_phone_override(self):
        raw = RawObject(
            source_object_id="T1", developer_name="D", jk_name="J",
            flat_number="1", floor="1", rooms="1", total_area="30",
            price="3000000", phone="1111111111",
        )
        u = normalize_object(raw, source_id=1, phone_override="+73852000000")
        assert u.phone == "73852000000"

    def test_studio_room(self):
        raw = RawObject(
            source_object_id="T2", developer_name="D", jk_name="J",
            flat_number="1", floor="1", rooms="студия", total_area="25",
            price="2500000", phone="73852111222",
        )
        u = normalize_object(raw, source_id=1)
        assert u.rooms == 0

    def test_price_in_thousands(self):
        raw = RawObject(
            source_object_id="T3", developer_name="D", jk_name="J",
            flat_number="1", floor="1", rooms="1", total_area="30",
            price="3500 тыс. руб.", phone="73852111222",
        )
        u = normalize_object(raw, source_id=1)
        assert u.price == 3500000
