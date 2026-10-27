import duckdb
from pathlib import Path
db_path=Path("data/database/pipeline.db")
con = duckdb.connect(str(db_path))

con.execute("""
    CREATE OR REPLACE TABLE vehicles_checked AS
    SELECT v.*,
    CASE WHEN v.dealer_id IN (SELECT dealer_id FROM raw_dealers) THEN 'ok'
    ELSE 'dealer_missing_from_raw_dealers'
    END AS quarantine_reason
    FROM raw_vehicles v
            """)

con.execute("""
    CREATE OR REPLACE TABLE clean_vehicles AS
    SELECT * FROM vehicles_checked
    WHERE quarantine_reason='ok'
    """)

con.execute("""
    CREATE OR REPLACE TABLE quarantine_vehicles AS
    SELECT * FROM vehicles_checked
    WHERE quarantine_reason != 'ok'
    """)

total=con.execute("SELECT COUNT(*) FROM vehicles_checked").fetchone()[0]
print("vehicles_checked:",total)

clean=con.execute("SELECT COUNT(*) FROM clean_vehicles").fetchone()[0]
print("clean_vehicles:",clean)

bad=con.execute("SELECT COUNT(*) FROM quarantine_vehicles").fetchone()[0]
print("quarantine_vehicles:",bad)
