import duckdb
from pathlib import Path

db_path=Path("data/database/pipeline.db")
con=duckdb.connect(str(db_path))

con.execute("""
    CREATE OR REPLACE TABLE dealer_id_counts AS
    SELECT dealer_id,COUNT(*) AS how_many
    FROM raw_dealers
    GROUP BY dealer_id
            """)

con.execute("""
    CREATE OR REPLACE TABLE dealers_checked AS
    SELECT
        d.*,
        CASE
            WHEN d.dealer_id IS NULL OR d.dealer_id='' THEN 'dealer_id_missing'
            WHEN d.dealer_id IN (SELECT dealer_id FROM dealer_id_counts WHERE how_many>1) THEN 'dealer_id_duplicated'
            ELSE 'ok'
        END AS quarantine_reason
    FROM raw_dealers d
            """)
            
con.execute("""
    CREATE OR REPLACE TABLE clean_dealers AS
    SELECT * FROM dealers_checked
    WHERE quarantine_reason='ok'
    """)

con.execute("""
    CREATE OR REPLACE TABLE quarantine_dealers AS
    SELECT * FROM dealers_checked
    WHERE quarantine_reason!='ok'
        """)

total=con.execute("SELECT COUNT(*) FROM dealers_checked").fetchone()[0]
print("dealers_checked:",total)

clean=con.execute("SELECT COUNT(*) FROM clean_dealers").fetchone()[0]
print("clean_dealers:",clean)

bad=con.execute("SELECT COUNT(*) FROM quarantine_dealers").fetchone()[0]
print("quarantine_dealers:",bad)
