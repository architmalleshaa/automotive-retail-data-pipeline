import duckdb
from pathlib import Path

db_path=Path("data/database/pipeline.db")
db_path.parent.mkdir(parents=True,exist_ok=True)

con= duckdb.connect(str(db_path))

tables = [
    ("raw_dealers", "data/raw/dealers.csv"),
    ("raw_vehicles","data/raw/vehicles.csv"),
    ("raw_listings","data/raw/listings.csv"),
    ("raw_customers","data/raw/customers.csv"),
    ("raw_inquiries","data/raw/inquiries.csv"),
    ("raw_sales", "data/raw/sales.csv"),
    ]

for table_name,csv_file in tables:
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} AS
        SELECT * FROM read_csv_auto(?)
    """,[csv_file])
    count=con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"Rows loaded into {table_name}:{count}")
con.close()
    
    
