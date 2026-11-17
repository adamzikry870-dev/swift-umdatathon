# Swift UMDAC Datathon 2026 — Dataset Anatomy & Reconstructed Generation Rules
### Working note 01: what the file is, how it is built, and how we know

Confidence tags: **[V]** verified on all 10M rows · **[S]** strong (large-sample, >99% consistent) · **[T]** tentative / still being tested

---

## 1. What the file physically is

| Property | Value |
|---|---|
| Rows | 10,000,000 payment records |
| Columns | 20 |
| Raw size | ~5 GB CSV (col 0 = quoted multi-line DISCLAIMER on the first line) |
| Time span | 2023-04-30 19:22 → 2023-07-31 17:56 UTC (92 days, ~108k payments/day) |
| Distinct timestamps | 5,085,929 second-level values — timestamps are true second-resolution instants, not day buckets |
| Currencies | 155 |
| Ordering banks (BIC8) | 8,392 |
| Beneficiary banks (BIC8) | 8,266 |
| USD_AMOUNT | mean 97,204 · median 3,662 · max 15.66 bn |
| TOTAL_DURATION | mean 771 s · median 56 s · max 21,649 s (6.0 h) |
| Labelled anomalies | 6,924 rows = 0.069% |

One row = **one payment message leg as observed on the Swift network**: who sent it, who received it, which banks it passed through, in which currency, how much, when, how long it took, plus masked party text.

The CSV is *not* sorted by time — it is a random-order export.

---

## 2. The 20 columns, grouped by role

| Group | Columns | Role |
|---|---|---|
| Timing | `EPOCH_SECONDS` | initiation instant (UTC seconds) |
| Money | `CURRENCY_CODE`, `USD_AMOUNT` | payment currency + USD-converted value |
| Route | `ORDERING_BIC8`, `BENEFICIARY_BIC8`, `BIC8_PATH`, `PARTICIPANT_COUNT`, `TRANSACTION_TYPE_CODE`, `CONTINUITY_QFLAG` | the bank chain and its labels |
| FX | `CURRENCY_CONVERSION_COUNT` | how many times the currency changed along the chain |
| Latency | `TOTAL_DURATION` | end-to-end seconds |
| Party identity | `ORDERING_ACCOUNT`, `BENEFICIARY_ACCOUNT` | IBAN-like fake account numbers |
| Party text | `ORDERING_DETAILS`, `BENEFICIARY_DETAILS`, `ORDERING_TOKENS`, `BENEFICIARY_TOKENS` | Faker-generated name/address block + a tokenised template of it |
| Party class | `ORDERING_TYPE`, `BENEFICIARY_TYPE` | `B` = business, `C` = consumer |
| Label | `ANOMALY_TYPE` | empty for 99.93% of rows |

### BIC8 anatomy **[V]**
`0621US30` = bank code `0621` + ISO country `US` + location `30`. Country is always characters 5–6. There is no real bank directory behind the codes — codes are enumerated `0001…0988` per country, so bank "identity" is synthetic and country is the only meaningful geography.

---

## 3. Structural invariants (the "hard-coded rules")

These are exact, 1:1 relationships — the strongest evidence of deliberate construction.

### 3.1 `PARTICIPANT_COUNT` = number of visible BIC nodes **[V]**
Path segments = participants + number of `...` gaps. `A;B;C` → 3 participants; `A;...;B` → 2 participants + 1 hidden hop.

### 3.2 `TRANSACTION_TYPE_CODE` is a pure function of participant count **[V]**
- `Direct` ⟺ exactly 2 participants (6,323,280 rows, 63.2%)
- `Indirect` or `Covered` ⟺ ≥3 participants

`Indirect` and `Covered` share the *same* geometric length distribution: P(k) ≈ 0.63 · 0.37^(k−2) for Indirect, P(k) ≈ 0.63 · 0.37^(k−3) for Covered. In other words the generator first decides the number of hops with a coin (stop probability ≈ 0.37 per extra hop), then assigns the label.

### 3.3 `CURRENCY_CONVERSION_COUNT` = number of adjacent currency changes along the path **[V]**
Verified on 800k rows with a derived country→dominant-currency map: 100% match. Max conversion count = participants − 1. Direct payments: 84.3% have exactly 1 conversion.

**This is the single most useful reverse-engineering lever in the dataset**: it means each BIC carries a deterministic "home currency", and the payment currency is *the ordering bank's home currency*. The map is not real-world (e.g. `BQ→USD`), so it must be recovered from data, not from an FX table.

### 3.4 `CONTINUITY_QFLAG` = `N` ⟺ the path contains `...` **[V]**
Exactly 767,204 rows are `N`, and `ell_share` is 1.000 in that group and 0.000 in the `Y` group. Semantics: **`N` = the chain is broken/truncated** (one or more correspondents hidden), `Y` = fully visible chain. Rows with `N` also carry more participants (3.12 vs 2.54) and more conversions (1.80 vs 1.30) on average, i.e. longer routes are more likely to be truncated.

Hidden-hop count is itself geometric: ~7.1% of payments show one gap, 0.55% two, and so on.

### 3.5 Accounts and countries **[V]**
- `ORDERING_ACCOUNT` looks like `_FAKE_` + IBAN-ish string, whose country prefix equals the ordering BIC country in **100%** of rows; same for beneficiary.
- 391,132 distinct ordering accounts (heavy-tailed reuse: 130k used once, top account 75,803 times), 2,590,877 distinct beneficiary accounts.
- Each ordering account is permanently bound to one country **and one `ORDERING_TYPE`** — parties are drawn as reusable entities, not generated per payment.

### 3.6 Party text country **[V]**
- `ORDERING_DETAILS` country token = ordering BIC country whenever present (39% of rows have no country token at all).
- `BENEFICIARY_DETAILS` country is **independent** of the beneficiary BIC country (~0.1% match). It is a separate draw, skewed to emerging economies (CN 8.8%, BR 5.5%, UA 4.4%, ET 3.5%, IN 2.8%, MX 2.6%).

Interpretation: the ordering party's address is "where the bank is" (domestic customer), while the beneficiary is "someone abroad" — the generator models a remittance/correspondent world, not a corporate treasury world.

`ORDERING_TOKENS` / `BENEFICIARY_TOKENS` are **deterministic pattern summaries** of the details string: vocabulary `chr`, `street:N`, `city:CC:N`, `country_code:CC`, `country_name:CC:en-gb`, `line_break:35/70`, `iban:22`, `business:N`, `company_keyword:N`, `first_name:N`, `last_name:N`, `post_code:CC:N`, `other_words:N`, `numerical:N`, `separator`, `stop_word`, `finance_word`, `truncation`. The `:N` is the token length, so tokens are reversible to the masked text.

---

## 4. The economic layer: how values were generated

### 4.1 Time: a universal "local business clock" **[S]**
Every country's hour-of-day histogram is the *same curve*, circularly shifted by its real UTC offset (correlation ≈0.999 vs the US curve; Europe +6 h, GB +5, SG/CN +13, JP +14, AU +16, BR +2, ZA +7, AE +9, IN +10).

So the generator drew a **local wall-clock time** from one global activity curve, then converted to UTC. Consequences:
- the timestamp's UTC hour is *not* a behavioural variable — it is (local hour + timezone);
- any "hour of day" dashboard must be localised or it will show a meaningless 24-hour smear.

Volume also has a calendar layer: weekday ≫ weekend (Fri 18.6% of the week, Sun 5.5%), plus strong week-to-week intensity variation; the first and last days are partial.

### 4.2 FX: a daily rate table with a weekend freeze **[S]**
Local-currency round amounts converted to USD at a per-day rate. Rates move smoothly day to day and **weekends repeat Friday's rate** — a classic synthetic-data tell. Recovered EUR series: 1.1007 → 1.2177, mean 1.1532, sd 0.0263, and it is *identical* whether estimated from 100-, 1,000- or 10,000-unit bands, confirming a single daily multiplier.

Recovered approximate levels: GBP 1.30, CHF 1.26, SGD 0.71, CNY 0.146, INR 0.0104, MYR 0.253, JPY ~0.0063 — close to real 2023 levels but randomised (the disclaimer says GDP/population/FX-like quantities were deliberately perturbed).

### 4.3 Amount: party-class scale × round-number snapping **[S]**
Median USD amount by party pair:

| Ordering → Beneficiary | Median USD |
|---|---|
| B → B | 22,888 |
| B → C | 3,119 |
| C → B | 3,229 |
| C → C | 463 |

≈ ×7 per business side, i.e. a multiplicative "who is paying whom" factor, with a lognormal body (σ ≈ 2.29 in log-USD) and a heavy tail.

On top of that, amounts are drawn in the **local currency** and snapped to human-preferred values (100, 500, 1,000, 5,000, 10,000, 50,000 …), then converted. This explains the whole-dollar lattice: 38.6% of USD payments are whole dollars vs ~1% of non-USD payments.

### 4.4 Currency choice **[S]**
Payment currency = ordering country's dominant currency in 85–95% of rows (EUR zone 93–95%, others 80–89%); otherwise a foreign currency (USD/EUR/GBP…) is used. This is the mechanism that produces `CURRENCY_CONVERSION_COUNT > 0`.

### 4.5 Routing: a popularity-weighted correspondent graph **[S/T]**
- 2.23 M distinct directed bank edges, 15 M path transitions.
- Intermediate banks are drawn from country weights that look like financial-centre shares; ordering and beneficiary bank countries are near-independent draws from similar weights (same-country only 7.1%).
- Some bank pairs repeat thousands of times (`0001MQM0→0009TNT0` 13,343 times, `0032MYK0→0010ALT0` 11,313) — hub structure, not uniform random.
- Ellipses are applied *after* the route is built, with a geometric gap count.

### 4.6 Latency: a route constant plus tiny noise **[S]**
For a given ordered bank pair, `TOTAL_DURATION` is essentially deterministic:

| Pair | n | median | sd | range |
|---|---|---|---|---|
| 0001MQM0→0009TNT0 | 12,642 | 1,594 s | 6.9 | 1,586–1,643 |
| 0032MYK0→0010ALT0 | 10,628 | 25 s | 33 | 12–3,354 |
| 0065SGS0→0472US30 | 6,924 | 923 s | 7.0 | 915–970 |

The residual noise is small and right-skewed (mode ≈ −5 s, 95th pct ≈ +20 s, sd ≈ 7 s). So latency ≈ **route constant + jitter**, not a behavioural wait time.

The route constants are **approximately additive in bank-level effects** (origin effect + beneficiary effect explain R² ≈ 0.99 of the variation across 18,063 bank pairs), and the bank effects are heavy-tailed: some banks add ~5–20 s, others ~1,000–5,000 s. Country-pair medians therefore span ~9 s to ~7,400 s purely because different banks are involved.

Practical implication: `TOTAL_DURATION` is a **route fingerprint**. It barely depends on amount, hour or weekday, so it can be used to check "is this payment's latency consistent with its stated path?" — a strong anomaly-detection feature.

### 4.7 Anomaly injection: labelled mutations of otherwise normal rows **[S/T]**
Only 0.069% of rows are labelled, and each label has a distinct mechanical signature:

| Label | n | Signature |
|---|---|---|
| ROMANCE_SCAM | 2,476 | ordering type `C` only; 500 distinct sender accounts, 378 beneficiary accounts; repeated payments to the same beneficiary; median gap ~10 min; median amount $109; currencies skew INR/CNY |
| FAT_FINGER_MISTAKE | 1,940 | extreme USD amounts (median $260k, mean $90M) — decimal/comma shift (×10/×100/×1000) |
| CEO_SCAM | 945 | ordering type `B` only; mean $1.38M |
| DUPLICATE_PAYMENT | 679 | shares ordering account, beneficiary account, amount **and** currency with another row (2,624 exact duplicate groups exist); median gap ~36 min |
| ACCOUNT_REPLACEMENT_SCAM | 649 | same ordering account + same amount but a *different* beneficiary account |
| CUSTOMER_RECALL | 317 | undocumented in the brief; still under analysis |

Key insight: the anomaly is **not** a separate population — it is a small set of rows whose fields were mutated (or cloned) according to a rule. That is why duplicates exist among *unlabelled* rows too, and why unlabelled rows can still look anomalous.

---

## 5. Reconstructed generator pipeline (best current reconstruction)

```
1. WORLD SETUP
   - country list with weights (financial-centre-like), timezone, dominant currency
   - per country: N banks, BIC8 = f"{code:04d}" + country + location2
   - per currency: daily FX rate path (random walk, weekend = Friday)
   - global: local-hour activity curve, weekday factors, day-level intensity

2. PARTY SETUP  (reused entities)
   ordering  = (bank, account, type B/C)   # account ↔ country ↔ type fixed forever
   beneficiary = (bank, account, type B/C)
   details   = Faker text in the bank country's locale  (ordering)
               Faker text in an independently drawn beneficiary country (beneficiary)

3. ROUTE
   n_hops ~ Geometric(p≈0.37)  (Direct if 2 visible nodes)
   intermediates ~ bank popularity weights
   hide some hops with '...'  (geometric, ~7% one gap)
   -> BIC8_PATH, PARTICIPANT_COUNT, TRANSACTION_TYPE_CODE, CONTINUITY_QFLAG

4. MONEY
   currency = ordering country's currency with prob p(country), else foreign
   local_amount = round_snap(lognormal(median = f(type_o, type_b)))
   USD_AMOUNT = local_amount × fx[currency][day]

5. TIME
   day ~ intensity(weekday, week)
   local_hour ~ global_curve
   EPOCH_SECONDS = utc(local datetime, tz(country))

6. LATENCY
   base = g(origin bank) + g(beneficiary bank) (+ hop terms)
   TOTAL_DURATION = round(base + jitter)

7. ANOMALY INJECTION (0.07%)
   mutate or clone ~7k rows per the six/five rules above
```

---

## 6. Why this matters for the analysis / dashboard

1. **Don't trust real-world priors where the generator defines its own mapping.** Country→currency, FX levels, bank sizes and geography weights were randomised. Recover them from the data (we already have the currency map and the daily FX table).
2. **The 1:1 invariants are the skeleton.** Participant count, conversion count and continuity flag are deterministic functions of the path — any dashboard that treats them as independent KPIs is double-counting.
3. **Time must be localised** before any hour-of-day or "business hours" narrative.
4. **Amount must be read on two axes**: party class (×7 per business side) and currency (round-number lattice + FX day). A raw USD amount distribution mixes both.
5. **Latency is a route fingerprint, not a service-level metric.** Service-level stories should be framed as "route/correspondent speed", not "processing delay varies with customer behaviour".
6. **Anomalies are injected mutations**, so detection rules should be structural (same account+amount+beneficiary; amount jump vs the account's history; latency inconsistent with path), not purely statistical outliers.
