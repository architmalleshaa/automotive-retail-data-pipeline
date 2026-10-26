import duckdb
from pathlib import Path

db_path = Path("data/database/pipeline.db")
db_path.parent.mkdir(parents=True,exist_ok=True)

csv_path=Path("data/raw/dealers.csv")

con=duckdb.connect(str(db_path))

con.execute("""
    CREATE TABLE IF NOT EXISTS raw_dealers AS
    SELECT * FROM read_csv_auto(?)
""",[str(csv_path)])

count = con.execute("SELECT COUNT(*) FROM raw_dealers").fetchone()[0]
print("Rows loaded into raw_dealers:", count)

con.close()
