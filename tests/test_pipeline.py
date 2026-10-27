import duckdb
from pathlib import Path

db_path=Path("data/database/pipeline.db")

def count(table):
    con=duckdb.connect(str(db_path))
    answer=con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    con.close()
    return answer

def test_dealers_split_adds_up():
    assert count("clean_dealers")+count("quarantine_dealers")==count("dealers_checked")

def test_vehicles_split_adds_up():
    assert count("clean_vehicles") + count("quarantine_vehicles") == count("vehicles_checked")

def test_listings_split_adds_up():
    assert count("clean_listings") + count("quarantine_listings") == count("listings_checked")


def test_clean_listings_have_real_vehicles():
    con=duckdb.connect(str(db_path))
    bad=con.execute("""
        SELECT COUNT(*) FROM clean_listings
        WHERE vin NOT IN (SELECT vin FROM clean_vehicles)
    """).fetchone()[0]
    con.close()
    assert bad == 0

def test_clean_vehicles_have_real_dealers():
    con=duckdb.connect(str(db_path))
    bad=con.execute("""
        SELECT COUNT(*) FROM clean_vehicles
        WHERE dealer_id NOT IN (SELECT dealer_id FROM clean_dealers)
    """).fetchone()[0]
    con.close()
    assert bad == 0

def test_clean_dealers_have_no_duplicate_ids():
    con=duckdb.connect(str(db_path))
    total=con.execute("SELECT COUNT(*) FROM clean_dealers").fetchone()[0]
    distinct=con.execute("SELECT COUNT(DISTINCT dealer_id) FROM clean_dealers").fetchone()[0]
    con.close()
    assert total==distinct
    


