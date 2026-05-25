# Belgium seven-country comparability update

Snapshot set: BE 2026-05-01, IE 2026-05-16, PL 2026-04-01, CZ 2026-05-20, ES/IT 2026-05-22, PT 2026-05-23.

Method: selected rows from the multinational lane index under comparable lane
`manufacturer_price / vat_exclusive / no_standard_margins`. For each country
and molecule, the table uses the lowest comparable `price_per_strength_unit_eur`
within the same INN, strength, form, and route identity key. BE, CZ, and PL are
observed manufacturer-price lanes; IE/ES/IT/PT are policy-derived manufacturer
lanes.

| Molecule | Identity key | BE EUR/mg | Seven-country median EUR/mg | BE vs median | Lowest | Highest |
|---|---:|---:|---:|---:|---|---|
| atorvastatin | 20 mg oral solid | 0.006923 | 0.005000 | 1.38x | CZ 0.001472 | ES 0.008236 |
| olanzapine | 10 mg oral solid | 0.032776 | 0.041000 | 0.80x | PL 0.031875 | ES 0.121001 |
| pantoprazole | 40 mg oral solid | 0.004140 | 0.002545 | 1.63x | PT 0.000392 | ES 0.009998 |
| clopidogrel | 75 mg oral solid | 0.001133 | 0.001581 | 0.72x | CZ 0.000973 | ES 0.004954 |
| dapagliflozin | 10 mg oral solid | 0.124000 | 0.106820 | 1.16x | PL 0.042388 | IT 0.133538 |

Brief readout: Belgium now enters the same seven-country manufacturer-price
comparison lane for all five validation drugs. It is above the seven-country
median for atorvastatin, pantoprazole, and dapagliflozin, and below the median
for olanzapine and clopidogrel. This update is an apple-to-apple validation of
the comparison substrate, not a net-price claim: confidential rebates remain
out of scope, and derived lanes are flagged as derived by policy intelligence.
