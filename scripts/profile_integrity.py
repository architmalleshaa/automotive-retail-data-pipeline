import duckdb
from pathlib import Path

db_path=Path("data/database/pipeline.db")
con=duckdb.connect(str(db_path))

checks=[(
            "Vehicles with no listing",
            """
            SELECT COUNT(DISTINCT v.vin)
            FROM raw_vehicles v
            LEFT JOIN raw_listings l ON v.vin =l.vin
            WHERE l.vin IS NULL
            """,
        ),
        (
            "Listings with no vehicle",
            """
            SELECT COUNT(DISTINCT l.listing_id)
            FROM raw_listings l
            LEFT JOIN raw_vehicles v ON l.vin=v.vin
            WHERE v.vin IS NULL
            """,
        ),
        (
            "Vehicles total rows",
            "SELECT COUNT(*) FROM raw_vehicles",
        ),
        (
            "Vehicles distinct VINs",
            "SELECT COUNT(DISTINCT vin) FROM raw_vehicles",
        ),
        (
            "Listings total rows",
            "SELECT COUNT(*) FROM raw_listings",
        ),
        (
            "Listings distinct IDs",
            "SELECT COUNT(DISTINCT listing_id) FROM raw_listings",
        ),
        ]
for label, query in checks:
    answer=con.execute(query).fetchone()[0]
    print(f"{label}:{answer}")
con.close()
 
