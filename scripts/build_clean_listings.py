import duckdb
from pathlib import Path
db_path=Path("data/database/pipeline.db")
con=duckdb.connect(str(db_path))

con.execute("""
    CREATE OR REPLACE TABLE listings_checked AS
    SELECT
        l.*,
        CASE
            WHEN l.vin IN (SELECT vin FROM clean_vehicles) THEN 'ok'
            ELSE 'vin_missing_from_clean_vehicles'
        END AS quarantine_reason
    FROM raw_listings l
""")
con.execute("""
    CREATE OR REPLACE TABLE clean_listings AS
    SELECT * FROM listings_checked
    WHERE quarantine_reason='ok'
""")
con.execute("""
    CREATE OR REPLACE TABLE quarantine_listings AS
    SELECT * FROM listings_checked
    WHERE quarantine_reason!='ok'
""")

total=con.execute("SELECT COUNT(*) FROM listings_checked").fetchone()[0]
print("listings_checked:",total)

clean=con.execute("SELECT COUNT(*) FROM clean_listings").fetchone()[0]
print("clean_listings:",clean)

bad=con.execute("SELECT COUNT(*) FROM quarantine_listings").fetchone()[0]
print("quarantine_listings:",bad)

