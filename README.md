# Automotive Retail Data Pipeline

A data engineering project that integrates dealership inventory, listings, customer inquiries, and sales into trusted analytics.

## Requirements

- Python 3.11 or newer. No third-party packages.

## Quick start

Clone the repo, then generate a small practice dataset and profile it:

```bash
python3 scripts/generate_synthetic_data.py --output data --preset practice
python3 scripts/profile_dealers.py
```

Run both commands from the project root. `profile_dealers.py` reads
`data/raw/dealers.csv` as a relative path, so it will not find the file
from anywhere else.

Expected output:

```
Repeated dealer_id: D004
Rows identical: True
Repeated dealer_id: D005
Rows identical: False
Total rows: 12
Rows missing dealer_id: 1
Different dealer_id values: 9
Repeated dealer_id rows: 2
Repeated rows matching first row: 1
Repeated rows differing from first row: 1
```

## What the profiler reports

`profile_dealers.py` inspects `dealers.csv` and reports three things:

- **Missing IDs** — rows with a blank `dealer_id`.
- **Repeated IDs that match** — the same row submitted twice. Harmless.
- **Repeated IDs that differ** — the same `dealer_id` on two different
  dealers. This is a broken identifier, not a duplicate row, and needs
  escalation to the source system rather than deletion.

The practice dataset contains one of each repeat type, so both paths
are exercised on a 12-row file.

## Full dataset

The full dataset is about 1 GB across six files and takes several minutes
to generate:

```bash
python3 scripts/generate_synthetic_data.py --output data --preset large
python3 scripts/profile_dealers.py
```

Results on the full dataset:

```
Total rows: 1006
Rows missing dealer_id: 3
Different dealer_id values: 997
Repeated dealer_id rows: 6
Repeated rows matching first row: 3
Repeated rows differing from first row: 3
```

Both presets use a fixed random seed, so generated files are identical
run to run and the numbers above are reproducible.

## Pipeline

The three cleaning scripts form a chain. A listing points at a vehicle, and a
vehicle points at a dealer, so each script checks its rows against the cleaned
output of the one above it.

Run them in this order:

```bash
python3 scripts/load_raw.py
python3 scripts/build_clean_dealers.py
python3 scripts/build_clean_vehicles.py
python3 scripts/build_clean_listings.py
```

Each script writes three tables into `data/database/pipeline.db`:

- `<table>_checked` — every raw row, unchanged, plus a `quarantine_reason`
  column holding `ok` or the name of the rule it failed.
- `clean_<table>` — the rows where `quarantine_reason` is `ok`.
- `quarantine_<table>` — everything else, complete rows with their reason
  attached.

Nothing is deleted. A quarantined row keeps every column it arrived with, so it
can be investigated and fixed at the source system rather than silently dropped.

The rules applied so far:

| Table | Rule | Reason written |
|---|---|---|
| dealers | `dealer_id` is blank | `dealer_id_missing` |
| dealers | `dealer_id` appears more than once | `dealer_id_duplicated` |
| vehicles | `dealer_id` is not in `clean_dealers` | `dealer_missing_from_clean_dealers` |
| listings | `vin` is not in `clean_vehicles` | `vin_missing_from_clean_vehicles` |

Current counts:

| Table | Total | Clean | Quarantined |
|---|---|---|---|
| dealers | 1,006 | 991 | 15 |
| vehicles | 2,008,918 | 1,986,563 | 22,355 |
| listings | 2,408,760 | 2,366,937 | 41,823 |

Both duplicate rows are quarantined, not just the second copy. When two rows
share a `dealer_id` but disagree on the name or city, there is no way to tell
which one is correct, so keeping either would be a guess.

## What the data looks like

Findings from `scripts/profile_integrity.py` and the three cleaning scripts:

- **41,823 listings advertise cars that are not in the clean vehicle set.**
  These are customer-facing ads with no vehicle behind them.
- **22,355 vehicles belong to a dealer that is not in the clean dealer set.**
  These cars cannot be traced to a dealership.
- **15 of the 1,006 dealer rows are unusable** — 3 with a blank `dealer_id`,
  and 12 rows sharing 6 duplicated `dealer_id` values.
- **7,360 vehicles have no listing at all** — inventory that no customer can
  see, and therefore cannot sell.
- **13,377 duplicate VIN rows in `raw_vehicles`** (2,008,918 rows against
  1,995,541 distinct VINs) and **13,140 duplicate `listing_id` rows in
  `raw_listings`** (2,408,760 against 2,395,620).
- **`mileage` and `list_price` load as text, not numbers.** A single bad value
  in a column forces the whole column to `VARCHAR`, so no arithmetic is
  possible until those columns are cleaned.

Cleaning the dealers changed the counts further down the chain without any new
rules being written. Pointing the vehicles check at `clean_dealers` moved 11,980
more cars into quarantine, and those cars in turn moved 14,321 more listings
into quarantine. That is the chain working as intended.

## Business question: which dealers have invisible inventory?

A vehicle with no listing cannot be seen by a customer, so it cannot sell. It
occupies space on the lot and loses value while it sits there. This script
ranks dealers by how many of their vehicles have no listing at all.

```bash
python3 scripts/analyze_unlisted_inventory.py
```

It reads `clean_vehicles` and `clean_listings`, keeps the vehicles whose `vin`
appears nowhere in `clean_listings`, groups them by `dealer_id`, and joins
`clean_dealers` for the dealership name.

Top 10 on the current dataset:

```
D597 Chicago Motor Group 0597 17
D940 Chicago Motor Group 0940 16
D881 Fishers Motor Group 0881 16
D748 Columbus Motor Group 0748 15
D096 Lexington Motor Group 0096 15
D049 Lexington Motor Group 0049 15
D324 Cleveland Motor Group 0324 15
D349 Grand Rapids Motor Group 0349 14
D082 Louisville Motor Group 0082 14
D424 Grand Rapids Motor Group 0424 14
```

The spread here is narrow because the synthetic generator distributes defects
evenly across dealers. On real inventory the distribution would be skewed, and
the top of this list is what an account manager would work through first.

The join uses `clean_dealers` rather than `raw_dealers` deliberately. The six
duplicated `dealer_id` values in the raw table would each match twice and
inflate the counts.