# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based property matching and monitoring tool for St. Petersburg, FL real estate. Fetches Zillow listings via RapidAPI, cross-references them against zoning databases (NTM-1 and Medical Office zones), sends email alerts via SendGrid, and updates an Airtable database.

## Running the Application

```bash
python main.py
```

Dependencies (no requirements.txt exists):
```bash
pip install requests pandas sendgrid airtable arcgis
```

## Architecture

### Core Workflow (`main.py`)

`main()` runs a linear pipeline:
1. **`get_property_data()`** — Fetches all Zillow listings (paginated), saves to `all_property_data.json` with timestamped backups
2. **`compare_NTMaddresses()`** — Matches listings against `NTMaddresses.csv`, generates HTML report with lot size color-coding (green ≥7260 SF, orange 5810–7260 SF) and map URLs
3. **`send_NTMproperty_matches()`** — Emails NTM matches via SendGrid
4. **`update_NTMairtable()`** — Inserts NTM matches into Airtable
5. 15-second pause between NTM and Health workflows
6. **`compare_HealthAddresses()`** — Matches listings against `HealthOfficeAddresses.csv`, excludes certain zone classes (NTM-1, RC-1, RC-2, RC-3), calculates price/SF of living area
7. **`send_Health_property_matches()`** — Emails Health zone matches to multiple recipients

### Supporting Files

- **`ntm1.py`** — ArcGIS data aggregation for NTM-1 zoning parcels
- **`addresshort.py`** — Address shortening utility via API

### Data Files

- `NTMaddresses.csv` — Target NTM-1 zoned addresses (single `Address` column)
- `HealthOfficeAddresses.csv` — Medical office addresses with `Address` and `Zone_Class` columns
- `all_property_data.json` — Current Zillow listings; date-stamped backups created each run

### External APIs

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Zillow RapidAPI | `zillow-com1.p.rapidapi.com/propertyExtendedSearch` | Property listings |
| St. Pete ArcGIS | `egis.stpete.org/arcgis/rest/services/` | Tax parcels, NTM zones, zoning data |
| SendGrid | API | HTML email delivery |
| Airtable | API | Property database storage |

### Jupyter Notebooks

Exploratory notebooks exist but are not part of the production workflow:
- `jupyter rapidapi zillow.ipynb` — Zillow API exploration
- `jupyter to medical office zoning.ipynb` — Medical zoning data processing

## Important Notes

- All API keys and credentials are hard-coded in `main.py` (SendGrid, RapidAPI, Airtable). There is no `.env` or config file.
- No test suite, linting config, or build system exists.
- Address matching uses string comparison after capitalizing Zillow addresses — the `capitalize_address()` helper normalizes suffixes (St→ST, Ave→AVE, etc.).
- The Airtable integration has had historical 403 permission errors; check token validity before relying on it.
- `ntm1.py` contains Windows-specific hardcoded file paths.
