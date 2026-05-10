from app.parsers.base import BaseParser, RawObject
from app.parsers.yandex import YandexParser
from app.parsers.avito import AvitoParser
from app.parsers.cian import CianParser
from app.parsers.custom_xml import CustomXmlParser
from app.parsers.excel import ExcelParser
from app.parsers.domclick import DomClickParser

PARSER_REGISTRY: dict[str, type[BaseParser]] = {
    # Standard formats
    "yandex": YandexParser,
    "avito": AvitoParser,
    "cian": CianParser,
    "custom_xml": CustomXmlParser,
    "excel": ExcelParser,
    # DomClick variants (all use the same parser)
    "domclick": DomClickParser,
    "domclick_pro": DomClickParser,   # macroserver domclickpro
    # Avito variants
    "avito_builder": AvitoParser,     # macroserver avito_builder (same format)
}


def get_parser(source_type: str) -> type[BaseParser]:
    """Return parser class for the given source type."""
    parser_cls = PARSER_REGISTRY.get(source_type)
    if not parser_cls:
        raise ValueError(
            f"Unknown source type: '{source_type}'. "
            f"Available: {sorted(PARSER_REGISTRY.keys())}"
        )
    return parser_cls
