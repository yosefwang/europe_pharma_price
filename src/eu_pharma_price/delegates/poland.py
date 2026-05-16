"""Poland country delegate."""

from .base import BaseDelegate


class PolandDelegate(BaseDelegate):
    country_code = "PL"
    default_currency = "PLN"
    delimiter = ";"
    decimal_separator = "."
    encoding = "utf-8"
    price_field = "CENA_HURTOWA_PLN"
    field_mapping = {
        "NAZWA": "product_name",
        "INN": "inn",
        "ATC": "atc_code",
        "DAWKA": "strength",
        "POSTAC": "dosage_form",
        "OPAKOWANIE": "pack_size",
        "PODMIOT": "manufacturer",
        "EAN": "national_product_code",
    }
    local_field_descriptions = {
        "CENA_HURTOWA_PLN": (
            "Wholesale price (cena hurtowa) in Polish złoty, as published in "
            "the Ministry of Health reimbursement list. This represents the "
            "price at which wholesalers supply pharmacies, including any "
            "applicable wholesale margin but before pharmacy margin and VAT."
        ),
        "EAN": (
            "International EAN-13 barcode used by the Polish Ministry of "
            "Health. Internationally interoperable in principle, but the "
            "publication regime treats it as a Polish national identifier."
        ),
    }
