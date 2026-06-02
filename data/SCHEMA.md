# Data dictionary

How the extracted datasets are structured. Regenerate everything with:

```bash
python tools/extract_metadata.py    # PDFs  → data/whitepapers.{json,csv}
python tools/generate_index.py      # JSON  → data/INDEX.md, data/STATS.md
python tools/build_site.py          # JSON  → search-index.json, text/
```

## `whitepapers.json`

Array of records, one per PDF:

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | File name without extension (the project title) |
| `file` | string | Original PDF file name |
| `size_bytes` | int | PDF size on disk |
| `has_text` | bool | `false` = scanned/image-only PDF, no metadata extracted |
| `wallets` | object | `{ eth_evm: [...], btc_bech32: [...], btc_legacy: [...] }` (keys present only when found) |
| `socials` | object | `{ platform: [handle, ...] }` for twitter, telegram, discord, github, linkedin, reddit, medium, facebook |
| `dates.full_dates` | string[] | Full dates found (e.g. `"January 5, 2018"`) |
| `dates.likely_year` | int \| null | Most frequently cited plausible publication year |
| `dates.year_range` | [int, int] \| null | Min/max year mentioned |
| `people.team` | string[] | Names sitting next to a role keyword (CEO/CTO/founder/advisor…) — high precision |
| `people.authors` | string[] | Names from the title block — lower precision |

## `whitepapers.csv`

Flat one-row-per-paper summary: `name, file, likely_year, wallets (count), socials, team, authors, has_text`.

## `INDEX.md`

Human-readable, A–Z table of every paper with year, team, first social handle, and first wallet. Generated — do not edit by hand.

## `STATS.md`

Aggregate counts and charts, embedded into the README.

## `search-index.json`

Compact index powering the [search site](https://immike.github.io/Crypto_Whitepapers/): `name, file, year, team, socials, social_text, wallets, snippet`.

## `text/<name>.txt`

Plain text of each paper (from `pdftotext`), committed so GitHub's code search indexes whitepaper *contents* and `tools/search.py` can do offline full-text search.

## ⚠️ Accuracy

Heuristic extraction. Wallet addresses may be examples/citations; team names may include occasional false positives; `likely_year` is inferred. Treat as leads, verify before relying. PRs with corrections welcome.
