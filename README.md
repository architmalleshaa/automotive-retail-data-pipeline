# Automotive Retail Data Pipeline

A data engineering project that integrates dealership inventory, listings, customer inquiries, and sales into trusted analytics.

## Requirements

- Python 3.11 or newer. No third-party packages.

## Quick start

Clone the repo, then generate a small practice dataset and profile it:

```bash
python3 scripts/generate_synthetic_data.py --output data/raw --preset practice
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
python3 scripts/generate_synthetic_data.py --output data/raw --preset large
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