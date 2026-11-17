# Swift UMDAC Datathon 2026 — analysis deliverables

Reverse-engineering of the synthetic cross-border payment dataset: how each field is
constructed, which causal rules the generator obeys, and the evidence for each rule.

Everything here is derived from the single supplied file
`swift_umdac_datathon_2026_fictitious_payment_data.csv` (10,000,000 rows). No external
data is used.

That file is **not** in this repository: at 4.95 GB it exceeds GitHub's limits and it is
the organisers' data to distribute. Everything downstream of it is committed, including
the panel CSVs and the rendered figures, so you can read and check the whole result
without it — and rebuild it from the raw CSV in about 20 minutes. See
[Running it yourself](#running-it-yourself).

## Read these first

| Document | What it is | Format |
|---|---|---|
| `docs/Swift_Dataset_Anatomy_and_Generation_Rules.pdf` | Field-by-field anatomy: what every column is, how it is generated, and the rules that tie columns together. | PDF (6 pp) · DOCX alongside |
| `docs/Swift_Dashboard_Specification.pdf` | The ten dashboard panels, each with its claim, the evidence drawn, the exact figures and the caveat. | PDF (7 pp) · DOCX alongside |
| `docs/Swift_Dashboard_Pack.pdf` | The ten exhibits themselves, one per landscape page, with a cover. | PDF (11 pp) |

## Repository layout

```
analysis/
  convert_csv.py                raw CSV → payments.parquet (once, ~8 min)
  build_data.py                 parquet → dashboard/data/*.csv
  verify.py                     re-derives every documented number, PASS/FAIL
  explore.py                    ad-hoc look at the data (schema, counts, queries)
  mdconvert.py                  one Markdown parser → DOCX and PDF writers
  verify_docs.py                document checks: page counts, all headings, no raw Markdown
  preview_docs.py               render PDF pages to PNG
  swift/                        the analysis package (imported by every entry point)
    db.py                       paths, DuckDB connection, country-from-BIC rule, CSV I/O
    panels.py                   the ten panel-data builders (one per dashboard section)
    rules.py                    the 52 checks behind the numbers quoted in the documents
  FINDINGS_01_dataset_overview.md    source of the anatomy document
  FINDINGS_02_dashboard_spec.md      source of the specification document
  archive.zip                   superseded exploration scripts + legacy CSVs, with a README
                                mapping each group to the module that replaced it
  payments.parquet              (not committed) the typed dataset, 1.26 GB
dashboard/
  build.py                      ten panels; one function each, registry at the bottom
  style.py                      palette, page furniture, axis formatters
  make_pack.py                  cover + panels → docs/Swift_Dashboard_Pack.pdf
  data/                         the CSVs/JSON each panel reads (auditable numbers)
  png/                          rendered panels at 200 dpi
docs/                           final deliverables (PDF + DOCX)
Datathon 2026 *.pdf             the organisers' handouts, reproduced here for context
```

The split matters: `swift/panels.py` writes every number a panel draws into
`dashboard/data/` as a CSV first, and `dashboard/build.py` only ever reads those
CSVs. No figure queries the parquet directly, so each claim can be audited from
the data file alone.

## Running it yourself

**1. Get the data.** The dataset is distributed by the organisers of the UMDAC Datathon
2026 preliminary round. Place the CSV at the repository root, keeping the exact name
`swift_umdac_datathon_2026_fictitious_payment_data.csv`. Nothing else is needed — no
downloads, no reference tables, no network access.

**2. Install the dependencies.**

```
git clone https://github.com/adamzikry870-dev/swift-umdatathon.git
cd swift-umdatathon
pip install -r requirements.txt
```

**3. Rebuild from the CSV.** Each step is independent and idempotent; skip any whose
output is already committed.

```
python analysis/convert_csv.py            # CSV → analysis/payments.parquet (once, ~8 min)
python analysis/build_data.py             # → dashboard/data/*.csv
python dashboard/build.py                 # → dashboard/png/*.png (or: build.py 3 7)
python dashboard/make_pack.py             # → docs/Swift_Dashboard_Pack.pdf
```

`build_data.py` rewrites all 21 panel files. Twenty come out byte-identical to the
committed ones; the twenty-first (`intermediary_concentration.csv`) can differ in its
cumulative column by up to 0.002 where two banks tie on count — see
[Known limitations](#known-limitations).

**4. Check the result.**

```
python analysis/verify.py          # 52 checks, ~2 min (--quick skips the two model fits)
python analysis/verify_docs.py     # 22 checks on the four documents and the pack
```

`verify.py` compares each number quoted in `docs/` with a fresh recomputation from
the parquet. `verify_docs.py` checks that every heading and table header from the
Markdown source survived into both the PDF and the DOCX, that page and paragraph
counts are unchanged, and that no Markdown syntax leaked into the output.

### Rebuilding the documents

The four documents in `docs/` are committed, so this is only needed after editing the
two Markdown sources.

```
python analysis/mdconvert.py analysis/FINDINGS_01_dataset_overview.md \
    docs/Swift_Dataset_Anatomy_and_Generation_Rules.docx "Dataset anatomy & generation rules"
python analysis/mdconvert.py analysis/FINDINGS_01_dataset_overview.md \
    docs/Swift_Dataset_Anatomy_and_Generation_Rules.pdf  "Dataset anatomy & generation rules"
python analysis/mdconvert.py analysis/FINDINGS_02_dashboard_spec.md \
    docs/Swift_Dashboard_Specification.docx "Dashboard Specification"
python analysis/mdconvert.py analysis/FINDINGS_02_dashboard_spec.md \
    docs/Swift_Dashboard_Specification.pdf  "Dashboard Specification"
```

`mdconvert.py` chooses the writer from the output suffix; the optional third
argument is the document title. A fourth argument overrides the running
header/footer line.

Both writers measure text with Calibri and Consolas. Rebuilding on macOS or Linux
produces the same content but may paginate differently, which will make
`verify_docs.py`'s page counts fail; the committed PDFs were built on Windows.

### Just want to look at the figures?

`dashboard/data/` and `dashboard/png/` are committed, so the rendering and pack steps
above work without the raw CSV:

```
python dashboard/build.py                 # → dashboard/png/*.png
python dashboard/make_pack.py             # → docs/Swift_Dashboard_Pack.pdf
```

## The five constants that explain most of the file

| Rule | Constant | Where |
|---|---|---|
| Currency is drawn from the sender's country | 89.4% local overall | panel 1 |
| Amount is set by the party pair | ×49 B→B vs C→C | panel 2 |
| Chain length is geometric | continue with p = 0.368 | panel 3 |
| Each hop is hidden with `...` | p = 0.0499, so gaps = 1 − 0.95^(n−1) | panel 4 |
| Each hop crosses a currency border | p = 0.851 | panel 5 |

Duration, the business-hours curve, the anomaly labels, correspondent concentration and the
free-text tokens are covered by panels 6–10.

## Known limitations

- `BIC8_PATH` is noisy: 5% of head hops and 5% of tail hops were replaced by a random
  different bank, so ~10% of payments end on a bank that is not the true origin or
  destination. All path-derived features describe the visible path.
- Anomaly typology names are the generator's labels, not a validated fraud taxonomy.
- The 19–23 June volume surge is unexplained and is treated as a scenario event.
- `intermediary_concentration.csv` orders tied banks by BIC, so its cumulative column can
  differ from the original by at most 0.002 where counts tie; the headline shares
  (19% / 52% / 93%) are unchanged.

## What came from where

- The dataset and the five `Datathon 2026 *.pdf` handouts at the repository root are the
  organisers' material, included unchanged (the dataset only by reference, since it is
  too large to host). All credit for those belongs to Universiti Malaya UMDAC and Swift.
- The analysis code, the panel CSVs, the figures and the four documents were produced for
  this entry.
- No third-party data or model is used anywhere in the pipeline.
