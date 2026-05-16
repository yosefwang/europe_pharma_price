# Policy Mapping — IE

_1 interpretation(s)._

## `EX_FACTORY_PRICE_EUR` → **Manufacturer-side price**

- **Interpretation ID:** `129f8938-8cd4-4e4a-b2cf-2702e0763641`
- **Effective:** 2021-08-01 — present
- **Confidence:** high
- **VAT included:** False
- **Margin:** none (excludes wholesale and pharmacy margin)

### Reading

EX_FACTORY_PRICE_EUR in the PCRS reimbursement list is the manufacturer ex-factory price excluding VAT and wholesale/pharmacy margin. Under FASPM the ex-factory price is the regulated price at which the marketing authorisation holder sells to the wholesale tier, and is the basis on which downstream payer reimbursement is computed.

### Source references

- https://www.hse.ie/eng/staff/pcrs/methodology/
- Framework Agreement on the Supply and Pricing of Medicines (FASPM) 2021

### Caveats

- PCRS publication also contains a RETAIL_PRICE_EUR column for some packs; do not confuse these.
- Ireland participates in BENELUXA reference-pricing arrangements; net prices may differ.
