import duckdb
from pathlib import Path

db_path=Path("data/database/pipeline.db")
con=duckdb.connect(str(db_path))

con.execute("""
    CREATE OR REPLACE TABLE unlisted_by_dealer AS
    SELECT dealer_id, COUNT(*) AS unlisted_cars
    FROM clean_vehicles
    WHERE vin NOT IN (SELECT vin FROM clean_listings)
    GROUP BY dealer_id
            """)
rows=con.execute("""
    SELECT u.dealer_id, d.dealer_name, u.unlisted_cars
    FROM unlisted_by_dealer u
    JOIN clean_dealers d ON u.dealer_id=d.dealer_id
    ORDER BY u.unlisted_cars DESC
    LIMIT 10
                """).fetchall()

print("Top 10 dealers by unlisted inventory")
for dealer_id, dealer_name, unlisted_cars in rows:
    print(dealer_id, dealer_name, unlisted_cars)
