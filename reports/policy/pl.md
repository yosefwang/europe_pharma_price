# Policy Mapping — PL

_1 interpretation(s)._

## `CENA_HURTOWA_PLN` → **Pharmacy purchase price**

- **Interpretation ID:** `1c9b1a07-12f3-4bef-8b37-ba36fbafb42a`
- **Effective:** 2012-01-01 — present
- **Confidence:** high
- **VAT included:** False
- **Margin:** wholesale margin only

### Reading

CENA_HURTOWA_PLN (cena hurtowa) is the regulated wholesale price in PLN under the Polish Reimbursement Act of 2011. It is the price at which wholesalers supply pharmacies, including a statutorily-bounded wholesale margin, but excluding the pharmacy margin and VAT.

### Source references

- Ustawa z dnia 12 maja 2011 r. o refundacji leków (Reimbursement Act of 12 May 2011)
- https://www.gov.pl/web/zdrowie/obwieszczenia-ministra-zdrowia-lista-lekow-refundowanych

### Caveats

- Includes wholesale margin; comparison to manufacturer-side categories from other countries requires a derivation rule (Phase 5).
- The list also publishes manufacturer price (cena zbytu netto) and retail price; CENA_HURTOWA_PLN is one of several fields in the same publication.
