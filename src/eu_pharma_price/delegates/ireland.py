"""Ireland country delegate."""

from .base import BaseDelegate


class IrelandDelegate(BaseDelegate):
    country_code = "IE"
    default_currency = "EUR"
    delimiter = ","
    decimal_separator = "."
    encoding = "utf-8"
    price_field = "EX_FACTORY_PRICE_EUR"
    field_mapping = {
        "PRODUCT_NAME": "product_name",
        "STRENGTH": "strength",
        "DOSAGE_FORM": "dosage_form",
        "PACK_SIZE": "pack_size",
        "MANUFACTURER": "manufacturer",
        "PRODUCT_CODE": "national_product_code",
    }
    local_field_descriptions = {
        "EX_FACTORY_PRICE_EUR": (
            "Manufacturer ex-factory price in euros, excluding VAT and "
            "wholesale/pharmacy margin, as published in the PCRS reimbursement "
            "list. This is the price at which the manufacturer sells to the "
            "wholesale level, before any downstream margin or tax is added."
        ),
        "PRODUCT_CODE": (
            "PCRS-assigned national product code. Stable per product/pack "
            "combination but country-specific — does not interoperate with "
            "EAN/CIP codes used in other registries."
        ),
    }
