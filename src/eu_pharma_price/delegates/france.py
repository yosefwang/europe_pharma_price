"""France country delegate."""

from .base import BaseDelegate


class FranceDelegate(BaseDelegate):
    country_code = "FR"
    default_currency = "EUR"
    delimiter = ","
    decimal_separator = "."
    encoding = "utf-8"
    price_field = "PRIX_FABRICANT_EUR"
    price_includes_vat = False
    field_mapping = {
        "DENOMINATION": "product_name",
        "INN": "inn",
        "ATC": "atc_code",
        "DOSAGE": "strength",
        "FORME": "dosage_form",
        "CONDITIONNEMENT": "pack_size",
        "LABORATOIRE": "manufacturer",
        "CIP13": "national_product_code",
    }
    local_field_descriptions = {
        "PRIX_FABRICANT_EUR": (
            "Manufacturer price (prix fabricant hors taxes, PFHT) in euros, "
            "as published in the Ameli base. This is the regulated price at "
            "which the marketing authorisation holder sells, before wholesale "
            "and pharmacy margins and before VAT."
        ),
        "CIP13": (
            "Code Identifiant de Présentation à 13 chiffres — the French "
            "national product identifier, country-specific. Different from "
            "the EAN used in some other regimes."
        ),
    }
