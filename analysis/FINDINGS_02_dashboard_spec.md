# Dashboard Specification and Evidence Notes

**Project:** Swift UMDAC Datathon 2026 — synthetic cross-border payment data
**Scope:** ten-panel exhibit pack, `docs/Swift_Dashboard_Pack.pdf`
**Data:** `analysis/payments.parquet`, 10,000,000 records, typed from the supplied CSV
**Companion:** `docs/Swift_Dataset_Anatomy_and_Generation_Rules.pdf` (field-by-field anatomy)

---

## 0. How to read this document

Every panel is presented in the same four-part structure:

- **Claim** — the one-sentence rule the panel exists to prove.
- **Evidence** — what is drawn and why that drawing is a test, not an illustration.
- **Numbers** — the exact figures quoted on the panel, so the reader can audit them.
- **Caveat** — the known limitation, so the claim is not over-read.
Three conventions apply throughout:

1. *Visible path* means `BIC8_PATH` as stored. Exactly 5% of head hops and 5% of tail hops were replaced by a random different bank in the generator, so 10% of payments end on a bank that is not the true origin or destination. Every path-derived feature in this pack is computed from the visible path, and the numbers therefore describe the file, not an unknowable ground truth.
2. *Participants* means the number of 8-character BIC nodes in the visible path, i.e. `PARTICIPANT_COUNT`.
3. All amounts are `USD_AMOUNT`; all counts are row counts over the full 10 million.

The generator reveals itself through constants. The pack is organised so that each panel isolates one constant:

| Panel | Constant or law | Value |
|---|---|---|
| 1 | local-currency probability | 84–95% per country, 89.4% overall |
| 2 | party-pair amount multiplier | ×6.7 to ×7.3 per business side, ×49.4 overall |
| 3 | continuation probability | 0.368 per extra bank (0.632 at k=3) |
| 4 | per-hop truncation probability | 0.0499 |
| 5 | per-hop currency-border probability | 0.851 |
| 6 | latency per hand-off | 38 → 804 s median, ×21 over 5 hops |
| 7 | business-hours curve | one shape, shifted by UTC offset |
| 8 | anomaly injection | 0.070% of rows, flat in chain length |
| 9 | correspondent concentration | top 100 banks = 51.9% of middle hops |
| 10 | address-token generation | 100% domestic / 1.0% foreign match |

---

## 1. Currency is chosen by the sender, not by the corridor

**Claim.** The payment currency is drawn from the ordering country's own currency with probability 0.84–0.95; when it is not local, the replacement is drawn from a global currency list dominated by EUR and USD, and is essentially unrelated to the beneficiary country.

**Evidence.** Left: local-currency share for the 20 largest ordering countries, with the all-country mean as a reference line. Right: composition of the non-local residual across the ten most frequent foreign currencies. If currency were corridor-driven, the local share would track the beneficiary mix; instead it sits in a narrow band for countries with wildly different corridor profiles (US, CH, DE all near 90%; AU and CA at 84%).

**Numbers.** Overall local share 89.4%. Lowest AU and CA 84%, highest ES 95%. Among the 10.6% non-local payments: EUR 44.0%, USD 21.9%, GBP 7.4%, CHF 5.5%, CNY 2.8%, SGD 2.2%, JPY 1.3%, HKD 1.2%, AUD 1.0%, AED 0.6%. EUR and USD together cover two thirds of the residual.

**Caveat.** The right panel is conditional on being non-local, so it cannot be read as a currency popularity ranking. The narrowness of the local-share band is a country-level statement; individual corridors inside a country can deviate, and the 5% path noise means the ordering country is wrong for about one row in twenty.

**Business meaning.** A currency feature is a sender-side attribute, not a trade-route attribute. Any model that learns "EUR corridor" is learning a proxy for the sender's home country, not a property of the beneficiary.

---

## 2. Who pays whom sets the amount — a 49× gap between B→B and C→C

**Claim.** Amount is generated from the party pair (business or consumer, ordering and beneficiary). The four pairs form an ordered ladder: B→B ≫ B→C ≈ C→B ≫ C→C, with a roughly constant multiplicative step per business side.

**Evidence.** The panel plots the cumulative distribution of `USD_AMOUNT` on a log axis for each party pair. A pure shift in log space appears as four parallel curves; they are parallel to within a few percentage points across the central 80% of the distribution. Median markers are placed at the 50% crossing.

**Numbers.** Medians: B→B 22,888; B→C 3,119; C→B 3,229; C→C 463. B→B is 49.4× C→C; each business side contributes about ×7 (B→C/C→C = 6.7; C→B/C→C = 7.0; B→B/B→C = 7.3). Means are far above medians (B→B 310,506; C→C 8,311), confirming a heavy right tail. 95th percentiles run 889,852 for B→B and 16,819 for C→C.

**Caveat.** The ladder is in log-amount, not in raw dollars; the constant multiplier does not mean the distributions are identical after rescaling (the tails differ). Medians are robust to the tail but the means are not.

**Business meaning.** Party type is the strongest single predictor of size, and it is available before the payment is sent. A model without party type will spend capacity re-learning this ladder through proxies such as bank identity or country.

---

## 3. Every extra bank in the chain is a 37% coin flip

**Claim.** Chain length is a geometric stopping process. Conditional on having k participants, the path continues to k+1 with probability 0.368, so the type-conditional length distribution is P(k) = 0.632 × 0.368^(k−3) for k ≥ 3. Direct payments are a hard exception: exactly two participants and no tail.

**Evidence.** Left panel: share of each transaction type at each length on a log y-axis, with the fitted geometric line. Indirect and Covered lie on the same line; Direct terminates at k=2. Right panel: the ratio of Covered to Indirect share at each k, with an identity line; if the two types shared one law the ratio is 1.00 at every k, which is what the panel shows (1.00, 1.00, 1.00, 1.00, 1.00, 1.01, 1.06).

**Numbers.** Direct: 6,323,280 rows, all at k=2. Indirect: 2,061,256 at k=3 falling to 1 at k=22; Covered: 263,063 at k=3 falling to 2 at k=15. Implied continuation probability 0.368 (decay factor per hop); 63.2% of non-direct payments stop at three participants. Maximum observed length is 22.

**Caveat.** The stop probability is estimated on the visible path; the 5% head/tail replacement can add or remove a node, which slightly fattens the tail. The ratio at k=9 is 1.06, i.e. Covered has a marginally heavier tail than Indirect — small enough to be sampling noise at n=685/1,770, but not zero.

**Business meaning.** Transaction type is a label on chain length, not an independent process. Given type and length, nothing else is needed to describe routing; and given length, type is almost redundant.

---

## 4. The strongest exact rule in the file: truncation is 1 − 0.95^(n−1)

**Claim.** Each hop of the path is independently collapsed into the literal token `...` with probability 0.0499. The probability that a payment shows at least one gap is therefore 1 − 0.95^(n−1), and the observed rate follows that curve to within sampling error at every length.

**Evidence.** Left: observed gap rate against the closed-form prediction with 95% confidence intervals on a 45° plot; the points sit on the diagonal. Right: standardised residuals, (observed − predicted) ÷ standard error, with ±2σ reference bands. This is the correct test: a 45° plot alone cannot distinguish a small systematic bias from noise when n is large.

**Numbers.** Per-hop gap probability 0.0499 (n=2 observed 4.99%). Gap rate by participants: 4.99%, 9.74%, 14.25%, 18.50%, 22.53%, 26.93%, 30.84%, 33.05%, 38.28%, 42.00%, 43.23% for n = 2…12. Predicted: 4.99%, 9.72%, 14.22%, 18.50%, 22.56%, 26.42%, 30.09%, 33.58%, 36.89%, 40.04%, 43.03%. 767,204 rows carry at least one gap. Residual z-scores range from −0.85 to +2.34; nine of eleven are inside ±2σ and none exceeds 2.4σ.

**Caveat.** Two points (n=7, z=2.34; n=8, z=2.01) sit marginally outside the 2σ line. With eleven tests at the 5% level, roughly half an excursion outside 2σ is expected by chance; the pattern is not evidence of a second rule, but the panel does not claim "all inside 95%". The baseline p is estimated from the n=2 rows themselves, so the tests are not fully independent.

**Business meaning.** Path completeness is not a data-quality accident; it is a per-hop disclosure choice with a fixed constant. Reconstructing hidden hops is possible only statistically, and the expected number of gap tokens is 0.0525 × (n−1).

---

## 5. Currency conversion is a property of the country chain, not a random event

**Claim.** `CURRENCY_CONVERSION_COUNT` is exactly the number of adjacent currency changes along the displayed path, using a country-to-currency map. Because each hop crosses a currency border with probability 0.851, the count follows Binomial(n−1, 0.851). The heat map shows the mechanism directly: pairs inside the euro area convert with probability 0 at every length, and only the diagonal is systematically zero elsewhere.

**Evidence.** Left: observed conversion-count shares for n = 2…7 against the binomial fit. Right: P(conversion) for direct payments between the 22 largest countries, grouped by home currency with gold separators. The pale EUR block is not missing data — it is a structural zero.

**Numbers.** Per-hop border probability 0.851. Maximum absolute deviation between observed and binomial share is 3.9 percentage points, at the far tail of the n=7 panel. Direct pairs take only the values 0 or 1; recomputing conversions from the displayed path reproduces the stored column on 100% of 1.5 million audited rows, with a maximum of n−1. The EUR–EUR block (FR, DE, IT, BE, LU, NL, FI, ES, AT) is 0 throughout; GB–IM (both GBP) is also zero off-diagonal.

**Caveat.** The single p=0.851 hides real heterogeneity: the per-hop probability is lower inside currency unions and higher across them, which is why the fit degrades at the n=7 tail. The binomial is a good description of the aggregate, not a generative claim about any one corridor.

**Business meaning.** Conversion count is derivable, not independent. It is a deterministic function of corridor geography and path length; using it as a free-standing feature risks double-counting the country chain.

---

## 6. Latency is bought by hand-offs, not by conversions

**Claim.** Duration is a property of the bank chain, not of the money. Holding conversions fixed, median `TOTAL_DURATION` rises 38 → 134 → 418 → 594 → 804 seconds as the chain grows from 2 to 6 participants. At a fixed chain length, moving from 0 to 5 conversions changes the median by at most 1.7× and not monotonically.

**Evidence.** Left: median duration versus participants at exactly one conversion, with p10 and p90 dashed and the p10–p90 band shaded; step multipliers annotated. Right: median duration versus conversion count, one line per chain length. If conversions cost time, the right-hand lines would slope upward; they are flat.

**Numbers.** Medians 38, 134, 418, 594, 804 s for n = 2…6 (21.2× end to end). p10: 13, 20, 30, 40, 54 s. p90: 2,321, 2,592, 2,940, 3,288, 3,710 s. Within a fixed n, the largest 0-to-max conversion span is 1.66× (n=3: 199 s at 0 conversions vs 120 s at 2). Step multipliers: ×3.5, ×3.1, ×1.4, ×1.35.

A separate set of tests (now `analysis/swift/rules.py`, `duration_models`; originally scripts `70_pairfit.py` to `81_dursplit.py`, both in the archived tree) rules out additive or max-of-banks latency: on a dense subgraph of repeated bank pairs an additive bank-effects model reaches R² = 0.21; a bank-identity model predicting held-out log duration reaches R² = 0.46; country-pair features reach 0.10. Within a single ordered bank pair, p90 − p10 is about 17 seconds, while across pairs medians span 9 s to 11,235 s.

**Caveat.** The flatness on the right is not evidence that conversions are *causally* free — conversions and chain length are jointly generated, and the panel holds length fixed to break the collinearity. The wide p10–p90 band shows that the median is a summary of a very heavy-tailed draw, not a promise for any single payment.

**Business meaning.** Duration is a fingerprint of the route. It leaks the hidden path (the duration matches the displayed path with median absolute error 4 s, versus 57.5 s if the true path is ignored), and it cannot be reconstructed from bank-level attributes. Treat it as an identifier-like property of the corridor.

---

## 7. One global business-hours curve, rotated by timezone

**Claim.** Every country's hourly volume profile is the same double-peaked business-hours curve, shifted by a constant number of hours. Stored timestamps are UTC, so the raw profiles look unrelated; after shifting, they collapse.

**Evidence.** Top left: share of each country's volume by stored hour for six countries; the curves are out of phase. Bottom left: the same curves after applying each country's best-fit shift, with the median pairwise correlation annotated. Right: daily volume with weekends highlighted and the June surge marked.

**Numbers.** Median alignment correlation 0.941 after shift (range 0.909–0.951 across the top 45 countries). Shifts: CH/FR/DE 0, SG/CN/HK/MY/TW 7, JP/KR 8, AU 10, US/CA/PA/KY/AR 18–20, GB/IM/IE/JE 23. Weekday volume 131,000–141,000 payments per day; Saturday 33,500 and Sunday 48,800, a 4.2× weekend trough. A five-day surge on 19–23 June reaches 204,804–220,212 per day. First and last calendar days are partial and excluded.

**Caveat.** The shift is chosen as the argmax of correlation, so it is an estimate, not a lookup from a timezone table; the values for GB (23) and US (18) are −1 and −6 modulo 24, consistent with UTC offsets but reported in the shift direction that aligns the curves. The June surge is unexplained by the generator and is treated as a scenario event, not a rule.

**Business meaning.** Time-of-day is a country-local business-cycle signal once detrended by the offset. Raw UTC hour is nearly useless on its own; hour adjusted by the ordering country's offset is the informative feature.

---

## 8. Anomalies are injected, not random: they cluster by typology and by destination

**Claim.** Anomaly labels are not sprinkled uniformly. They are typed, each type has a party-structure signature, the injection rate is flat through the common chain lengths, and the country-level rate is driven by destination, not by volume.

**Evidence.** Left: labelled anomalies per 100,000 payments by beneficiary bank country, top 16 countries with at least 1,000 payments, log axis, all-country reference line. Right: party mix inside each typology as a 100% stacked bar, so the structural signature is visible without counts.

**Numbers.** 7,006 labelled rows (0.070% of the file): ROMANCE_SCAM 2,476; FAT_FINGER_MISTAKE 1,940; CEO_SCAM 945; DUPLICATE_PAYMENT 679; ACCOUNT_REPLACEMENT_SCAM 649; CUSTOMER_RECALL 317.

Party mix: ROMANCE is 100% consumer-sent (26.9% C→B, 73.1% C→C); CEO is 100% business-sent (27.7% B→B, 72.3% B→C); the other four are business-heavy, with B→C between 56.6% and 57.9% and B→B between 19.9% and 22.9%.

Injection rate by chain length: 0.070%, 0.072%, 0.073%, 0.071% for n = 2…5, then 0.046%, 0.052%, 0.045% for n = 6…8 — flat across the common lengths, with a thinner tail.

Rates by beneficiary country: PK 7,914; MZ 6,750; EG 5,539; VE 4,143; ID 3,572; SY 2,400; SD 2,277; AO 2,275; ET 2,115; SS 1,668 per 100,000, against US 32.7 and an all-country mean of 70.7. Anomaly count correlates with corridor count at r = 0.655, and the per-corridor rate is flat at 0.0003–0.0004 across volume buckets. Within the largest single chain length (n=2, where all types appear), EG remains at 4,980 per 100,000 and ID at 3,997, so the country effect is not a chain-length artefact.

Amount fingerprints: FAT_FINGER amounts sit at 33.5× the median of their own corridor (p10 below 0.1×, p90 above 12,000×) — the extra-zero signature. ROMANCE amounts are small: 68.9% are under $500 versus 21.9% in unlabelled rows, median $109. CUSTOMER_RECALL and FAT_FINGER have normal duration (53 s median); ROMANCE 1,148 s, CEO 741 s, ACCOUNT_REPLACEMENT 571 s, DUPLICATE 261 s.

**Caveat.** The country ranking is a ranking of *labelled* anomalies, and the label rate is not independent of the generator's country sampling. The r = 0.655 with corridor count means the country effect is partly a portfolio-size effect; conditioning on chain length removes some but not all of it. The typology names are the generator's, not a ground-truth fraud taxonomy.

**Business meaning.** Anomaly detection should be type-aware and destination-aware. A single global threshold will either miss the high-rate destinations or flood on the low-rate ones; a per-corridor rate model with party-type features is the natural baseline.

---

## 9. A handful of banks carry the network

**Claim.** The correspondent graph is a hub-and-spoke network, not a uniform mesh. Bank population is spread over 228 countries, but a small number of institutions dominate the middle of the paths.

**Evidence.** Left: count of distinct BIC8 codes by ordering country for the top 14 countries. Right: cumulative share of intermediate hops by bank rank on a log x-axis, with markers at ranks 10, 100 and 1,000.

**Numbers.** 8,392 distinct banks across 228 countries. Largest populations: US 979, GB 583, FR 420, DE 386, CN 370, CH 283, HK 195, JP 184, SG 183. Intermediate-hop concentration: top 10 banks 19.2%, top 100 51.9%, top 1,000 92.8% (7,414 banks ever appear in a middle position).

**Caveat.** Concentration is measured on intermediate positions only, so it excludes direct payments and the two endpoints; a bank that is usually an origin or destination but rarely an intermediary looks small here. Counts are of distinct codes, not of institutions (one group can own several BICs).

**Business meaning.** Bank identity is informative but sparse: with 8,392 codes over 10 million rows, most banks have few observations. Country and currency-group aggregates are the stable representation of the same information.

---

## 10. The sender's address is domestic; the beneficiary's is anywhere

**Claim.** Party address text is generated independently of the payment's bank chain for the beneficiary, but is tied to the ordering bank's country for the sender. When a country token is present, the ordering address matches its bank country 100.0% of the time and the beneficiary address only 1.0%.

**Evidence.** Left: token agreement rates for the two parties, restricted to rows where a token exists (61% of the file). Right: for the ten largest address countries, the address share is compared with the same country's share of beneficiary banks; the ratio column makes the independence explicit.

**Numbers.** Ordering token present in 60.8% of rows, beneficiary token in 61.1%. Ordering match 100.0% (by construction); beneficiary match 0.98%. Beneficiary address shares: CN 8.8%, BR 5.5%, UA 4.4%, ET 3.5%, IN 2.8%, MX 2.6%, US 2.6%, JP 2.5%, KE 2.2%, BD 2.0%. Beneficiary bank shares: US 19.2%, CH 8.3%, GB 6.6%. Ratio of address share to bank share: CN 2.55×, BR 46.75×, UA 6.10×, ET 170.4×, IN 5.34×, MX 16.73×, US 0.13×, JP 1.47×, KE 81.72×, BD 9.83×.

**Caveat.** The 100% ordering match is a construction identity, not a discovered correlation; it should not be used as a model feature without noting that it leaks the label. The beneficiary match is 1.0%, which is close to but not exactly the chance rate implied by the country distribution; treat it as "independent draw with a small residual overlap".

**Business meaning.** Address tokens are usable as a *sender* feature and as a noise-like *beneficiary* feature. Any model that learns a beneficiary address → bank-country mapping will mostly learn noise.

---

## 11. What the construction rules imply for modelling

1. **Prefer generator variables over raw text.** Party type, chain length, country chain and currency chain explain most of the structure. Text fields are partly generated noise.
2. **Do not treat derived fields as independent.** Conversion count is a deterministic function of the country chain; transaction type is a label on chain length; continuity flag is a per-hop draw. Feeding all of them to a linear model creates exact collinearity.
3. **Respect the 5% path noise.** Features built from `BIC8_PATH` endpoints will be wrong for about 10% of rows. Aggregations by country and currency are more stable than bank-level joins.
4. **Model duration as a route effect, not a bank effect.** Bank-identity models plateau at R² ≈ 0.46 on held-out log duration; the route itself is the unit.
5. **Anomaly models need per-corridor baselines.** The label rate is 0.07% overall but spans 0.03% to 7.9% by destination; a global threshold is mis-specified.
6. **Cap the tail.** Amounts and durations are heavy-tailed; log transforms and quantile targets are safer than raw means (B→B mean is 13.6× its median).

---

## 12. Open questions

- **ACCOUNT_REPLACEMENT_SCAM (649 rows).** Structurally distinct in one respect: only 0.6% of rows are same-country, versus 7.1% for unlabelled rows, and median duration is 571 s against 56 s. The party mix is business-heavy (57.0% B→C). What we cannot yet show is the *trigger*: whether the label is attached to a specific beneficiary-bank change, a corridor, or a random draw within the constraint set.
- **CUSTOMER_RECALL (317 rows).** Appears on short chains only (n ≤ 4 in the filtered view), has normal duration (53 s) and normal amounts, and is spread over 64 beneficiary countries. It looks like a "routine operations" label rather than a fraud typology; its generating rule is not yet identified.
- **The June surge.** Five consecutive days at 205,000–220,000 payments are not explained by weekday, month or country mix. It is treated as a scenario event in panel 7; whether it is a deliberate seasonal injection is unresolved.
- **Why pc2 domestic pairs are slower.** Domestic two-bank routes have a pair-level median of 242 s versus 36 s for cross-border pairs (row-level 56 s vs 39 s). The mechanism is not identified; it is noted as a caveat on the "duration is a route fingerprint" claim.

---

## Appendix: reproduction

| Artefact | Script |
|---|---|
| Typed dataset | `analysis/convert_csv.py` (CSV → parquet) |
| Panel data | `analysis/build_data.py` → `analysis/swift/panels.py` |
| Documented numbers | `analysis/verify.py` → `analysis/swift/rules.py` (52 checks) |
| Panel rendering | `dashboard/build.py` (CLI: `python dashboard/build.py 1 2 …`) |
| PDF pack | `dashboard/make_pack.py` |
| This document | `analysis/FINDINGS_02_dashboard_spec.md` → `analysis/mdconvert.py` |
| Anomaly fingerprints | `analysis/swift/panels.py` (panel 8), `analysis/swift/rules.py` (anomalies) |
| Duration structure | `analysis/swift/panels.py` (panel 6), `analysis/swift/rules.py` (`duration_models`) |

The original numbered exploration scripts are kept, unmodified, in
`analysis/archive.zip` (unzip into `analysis/` to restore `analysis/archive/`); its
README maps each group to the module that superseded it.
