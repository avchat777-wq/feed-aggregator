"""Tests for all parser implementations."""

import pytest
from app.parsers.yandex import YandexParser
from app.parsers.avito import AvitoParser
from app.parsers.cian import CianParser
from app.parsers.custom_xml import CustomXmlParser
from app.parsers.excel import ExcelParser

SOURCE_CONFIG = {"name": "test", "developer_name": "TestDev", "mapping_config": None}


# ─────────────── Yandex Parser ───────────────

class TestYandexParser:
    SAMPLE_YRL = b"""<?xml version="1.0" encoding="UTF-8"?>
    <realty-feed>
        <offer internal-id="YA-001">
            <building-name>JK Solnechny</building-name>
            <apartment>42</apartment>
            <floor>5</floor>
            <floors-total>10</floors-total>
            <rooms>2</rooms>
            <area><value>65.5</value></area>
            <price><value>5500000</value></price>
            <sales-agent><phone>+7-385-253-3522</phone></sales-agent>
            <description>Nice apartment</description>
            <image>https://example.com/photo1.jpg</image>
        </offer>
        <offer internal-id="YA-002">
            <building-name>JK Solnechny</building-name>
            <apartment>43</apartment>
            <floor>6</floor>
            <rooms>1</rooms>
            <area><value>38.2</value></area>
            <price><value>3200000</value></price>
            <sales-agent><phone>+73852533522</phone></sales-agent>
        </offer>
    </realty-feed>"""

    def test_parse_valid(self):
        parser = YandexParser(SOURCE_CONFIG)
        result = parser.parse(self.SAMPLE_YRL)
        assert len(result) == 2
        assert result[0].source_object_id == "YA-001"
        assert result[0].jk_name == "JK Solnechny"
        assert result[0].flat_number == "42"
        assert result[0].floor == "5"
        assert result[0].rooms == "2"
        assert result[0].total_area == "65.5"
        assert result[0].price == "5500000"
        assert len(result[0].photos) == 1

    def test_parse_invalid_xml(self):
        parser = YandexParser(SOURCE_CONFIG)
        result = parser.parse(b"<invalid xml>")
        assert len(result) == 0
        assert len(parser.errors) > 0

    def test_parse_empty(self):
        parser = YandexParser(SOURCE_CONFIG)
        result = parser.parse(b"<realty-feed></realty-feed>")
        assert len(result) == 0


# ─────────────── Avito Parser ───────────────

class TestAvitoParser:
    SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
    <Ads>
        <Ad>
            <Id>AV-100</Id>
            <NewDevelopmentName>JK River</NewDevelopmentName>
            <FlatNumber>15</FlatNumber>
            <Floor>3</Floor>
            <Floors>9</Floors>
            <Rooms>3</Rooms>
            <Square>78.4</Square>
            <Price>6200000</Price>
            <ContactPhone>+73852111222</ContactPhone>
            <Description>Great view</Description>
            <Images><Image url="https://example.com/img1.jpg"/></Images>
        </Ad>
    </Ads>"""

    def test_parse_valid(self):
        parser = AvitoParser(SOURCE_CONFIG)
        result = parser.parse(self.SAMPLE)
        assert len(result) == 1
        assert result[0].source_object_id == "AV-100"
        assert result[0].jk_name == "JK River"
        assert result[0].rooms == "3"
        assert result[0].price == "6200000"

    def test_parse_empty(self):
        parser = AvitoParser(SOURCE_CONFIG)
        result = parser.parse(b"<Ads></Ads>")
        assert len(result) == 0


# ─────────────── CIAN Parser ───────────────

class TestCianParser:
    SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
    <Feed>
        <Feed_Version>2</Feed_Version>
        <Object>
            <ExternalId>CIAN-500</ExternalId>
            <Category>newBuildingFlatSale</Category>
            <JKSchema>
                <Id>5895</Id>
                <n>JK Sunny</n>
                <House>
                    <Id>577592</Id>
                    <n>Korpus 2</n>
                    <Flat>
                        <FlatNumber>105</FlatNumber>
                        <SectionNumber>1</SectionNumber>
                    </Flat>
                </House>
            </JKSchema>
            <FlatRoomsCount>2</FlatRoomsCount>
            <TotalArea>65.5</TotalArea>
            <FloorNumber>7</FloorNumber>
            <Decoration>fine</Decoration>
            <Phones>
                <PhoneSchema>
                    <CountryCode>+7</CountryCode>
                    <Number>3852533522</Number>
                </PhoneSchema>
            </Phones>
            <BargainTerms>
                <Price>8500000</Price>
                <SaleType>DDU</SaleType>
            </BargainTerms>
        </Object>
    </Feed>"""

    def test_parse_valid(self):
        parser = CianParser(SOURCE_CONFIG)
        result = parser.parse(self.SAMPLE)
        assert len(result) == 1
        obj = result[0]
        assert obj.source_object_id == "CIAN-500"
        assert obj.jk_name == "JK Sunny"
        assert obj.flat_number == "105"
        assert obj.house_name == "Korpus 2"
        assert obj.section_number == "1"
        assert obj.floor == "7"
        assert obj.rooms == "2"
        assert obj.price == "8500000"
        assert obj.phone == "73852533522"
        assert obj.sale_type == "DDU"
        assert obj.decoration == "fine"

    def test_jk_id_cian(self):
        parser = CianParser(SOURCE_CONFIG)
        result = parser.parse(self.SAMPLE)
        assert result[0].jk_id_cian == "5895"


# ─────────────── Custom XML Parser ───────────────

class TestCustomXmlParser:
    SAMPLE = b"""<data>
        <apartment>
            <id>CX-1</id>
            <complex>JK Custom</complex>
            <apt_num>22</apt_num>
            <fl>4</fl>
            <sqm>55.3</sqm>
            <cost>4800000</cost>
            <tel>+73852000111</tel>
        </apartment>
    </data>"""

    def test_parse_with_mapping(self):
        config = {
            **SOURCE_CONFIG,
            "mapping_config": {
                "item_xpath": "//apartment",
                "fields": {
                    "source_object_id": "./id/text()",
                    "jk_name": "./complex/text()",
                    "flat_number": "./apt_num/text()",
                    "floor": "./fl/text()",
                    "total_area": "./sqm/text()",
                    "price": "./cost/text()",
                    "phone": "./tel/text()",
                }
            }
        }
        parser = CustomXmlParser(config)
        result = parser.parse(self.SAMPLE)
        assert len(result) == 1
        assert result[0].jk_name == "JK Custom"
        assert result[0].flat_number == "22"
        assert result[0].price == "4800000"

    def test_parse_no_mapping(self):
        parser = CustomXmlParser(SOURCE_CONFIG)
        result = parser.parse(self.SAMPLE)
        assert len(result) == 0
        assert len(parser.errors) > 0


# ─────────────── Excel Parser ───────────────

class TestExcelParser:
    def test_parse_csv_content(self):
        csv_content = (
            "jk,flat,floor,rooms,area,price,phone\n"
            "JK Test,101,5,2,55.3,4500000,+73852111222\n"
            "JK Test,102,6,1,38.0,3200000,+73852111222\n"
        ).encode("utf-8")

        config = {
            **SOURCE_CONFIG,
            "mapping_config": {
                "header_row": 0,
                "fields": {
                    "jk": "jk_name",
                    "flat": "flat_number",
                    "floor": "floor",
                    "rooms": "rooms",
                    "area": "total_area",
                    "price": "price",
                    "phone": "phone",
                }
            }
        }

        parser = ExcelParser(config)
        result = parser.parse(csv_content)
        assert len(result) == 2
        assert result[0].jk_name == "JK Test"
        assert result[0].flat_number == "101"
        assert result[0].price == "4500000"
        assert result[1].flat_number == "102"
