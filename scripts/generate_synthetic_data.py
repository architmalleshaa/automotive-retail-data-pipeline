#!/usr/bin/env python3
"""Create reproducible connected CSV fixtures; this is not the ETL pipeline.

Python standard library only. No downloads, accounts, or third-party data.
Refuses to overwrite existing outputs. See docs/SYNTHETIC_DATA.md.
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path

VERSION = "1.0.0"
AS_OF = date(2026, 10, 19)
EPOCH = date(2018, 1, 1)
DATES = [(EPOCH + timedelta(days=i)).isoformat() for i in range(5000)]
AS_OF_DAY = (AS_OF - EPOCH).days
START_DAY = (date(2020, 1, 1) - EPOCH).days
END_SOLD_DAY = (date(2026, 8, 1) - EPOCH).days
SCHEMAS = {
    "dealers": ["dealer_id", "dealer_name", "city", "state", "opened_date", "active_status"],
    "vehicles": ["vin", "dealer_id", "year", "make", "model", "mileage", "acquired_date"],
    "listings": ["listing_id", "vin", "dealer_id", "list_price", "listed_date", "listing_status"],
    "customers": ["customer_id", "full_name", "email", "phone_number", "market_area", "created_date"],
    "inquiries": ["inquiry_id", "customer_id", "listing_id", "inquiry_channel", "inquiry_date", "inquiry_status"],
    "sales": ["sale_id", "vin", "customer_id", "inquiry_id", "sale_price", "sale_date"],
}
PRESETS = {
    "practice": {"dealers": 10, "vehicles": 1000, "customers": 1000},
    "large": {"dealers": 1000, "vehicles": 2_000_000, "customers": 2_000_000},
}
MARKETS = [
    ("Carmel", "IN", "317"), ("Indianapolis", "IN", "463"),
    ("Fishers", "IN", "317"), ("Fort Wayne", "IN", "260"),
    ("Bloomington", "IN", "812"), ("South Bend", "IN", "574"),
    ("Lafayette", "IN", "765"), ("Evansville", "IN", "812"),
    ("Columbus", "OH", "614"), ("Cincinnati", "OH", "513"),
    ("Cleveland", "OH", "216"), ("Chicago", "IL", "312"),
    ("Springfield", "IL", "217"), ("Louisville", "KY", "502"),
    ("Lexington", "KY", "859"), ("Detroit", "MI", "313"),
    ("Grand Rapids", "MI", "616"), ("Ann Arbor", "MI", "734"),
]
CARS = [
    ("Honda", "Accord", 33000), ("Honda", "Civic", 28000),
    ("Toyota", "Camry", 34000), ("Toyota", "Corolla", 27000),
    ("Ford", "F-150", 46000), ("Chevrolet", "Equinox", 33000),
    ("Nissan", "Altima", 30000), ("Hyundai", "Elantra", 26000),
    ("Subaru", "Outback", 36000), ("Kia", "Sportage", 32000),
    ("Jeep", "Grand Cherokee", 47000), ("Toyota", "RAV4", 37000),
]
FIRST = "Alex Jordan Taylor Morgan Casey Riley Avery Cameron Jamie Quinn Parker Drew Robin Jesse Sam Charlie Hayden Rowan Skyler Dakota".split()
LAST = "Smith Johnson Williams Brown Jones Garcia Miller Davis Wilson Anderson Thomas Moore Martin Lee Thompson White Harris Clark Lewis Robinson".split()
INQUIRY_COUNTS = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]
UNSOLD_POSITIONS = {9, 23, 40, 72, 95}
ISSUES = {
    "dealers": ["duplicate_exact", "duplicate_conflicting", "missing_dealer_id", "invalid_state", "invalid_opened_date", "invalid_active_status", "whitespace_name"],
    "vehicles": ["duplicate_exact", "duplicate_conflicting", "missing_vin", "orphan_dealer", "negative_mileage", "nonnumeric_mileage", "future_year", "invalid_acquired_date", "whitespace_vin"],
    "listings": ["duplicate_exact", "duplicate_conflicting", "missing_listing_id", "orphan_vin", "orphan_dealer", "dealer_mismatch", "negative_price", "nonnumeric_price", "listing_before_acquisition", "invalid_listing_status", "currency_formatted_price"],
    "customers": ["duplicate_exact", "duplicate_conflicting", "missing_customer_id", "missing_name", "invalid_email", "invalid_phone", "future_created_date", "whitespace_name", "email_case_and_spaces", "formatted_phone"],
    "inquiries": ["duplicate_exact", "duplicate_conflicting", "missing_inquiry_id", "orphan_customer", "orphan_listing", "inquiry_before_listing", "invalid_inquiry_date", "invalid_inquiry_status", "invalid_channel", "whitespace_customer_id"],
    "sales": ["duplicate_exact", "duplicate_conflicting", "missing_sale_id", "orphan_vin", "orphan_customer", "orphan_inquiry", "negative_price", "nonnumeric_price", "sale_before_inquiry", "sale_customer_mismatch", "sale_vehicle_mismatch", "future_sale_date"],
}
NORMALIZABLE = {"whitespace_name", "whitespace_vin", "currency_formatted_price", "email_case_and_spaces", "formatted_phone", "whitespace_customer_id"}


def mix(n, seed):
    """Stable integer mixing, independent of Python's randomized hash()."""
    x = (n + seed * 374761393) & 0xFFFFFFFF
    x = ((x ^ (x >> 16)) * 2246822519) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 3266489917) & 0xFFFFFFFF
    return x ^ (x >> 16)


def identifier(prefix, n):
    return f"{prefix}{n:09d}"


def vin(n):
    # Deliberately fictional 17-character keys, NOT road-valid VINs.
    return f"SYN{n:014d}"


def dealer_id(n):
    return f"D{n:03d}"


def inactive(n):
    return n == 3 or n % 31 == 0


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def csv_line(row):
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerow(row)
    return buffer.getvalue()


def changed_row(table, source, issue, context):
    row = dict(zip(SCHEMAS[table], source))
    if issue == "duplicate_exact":
        return list(source)
    if issue == "duplicate_conflicting":
        field = {"dealers": "dealer_name", "vehicles": "mileage", "listings": "list_price", "customers": "full_name", "inquiries": "inquiry_channel", "sales": "sale_price"}[table]
        row[field] = {"dealers": row.get(field, "") + " - conflicting export", "vehicles": "1", "listings": "1.00", "customers": "Conflicting Customer", "inquiries": "email" if row.get(field) != "email" else "phone", "sales": "1.00"}[table]
        if row[field] == source[SCHEMAS[table].index(field)]:
            row[field] = "2"
    elif issue.startswith("missing_"):
        field = "full_name" if issue == "missing_name" else issue.removeprefix("missing_")
        row[field] = ""
    elif issue.startswith("orphan_"):
        field = {"orphan_dealer": "dealer_id", "orphan_customer": "customer_id", "orphan_listing": "listing_id", "orphan_inquiry": "inquiry_id", "orphan_vin": "vin"}[issue]
        row[field] = {"dealer_id": "D999999999", "customer_id": "C999999999", "listing_id": "L999999999", "inquiry_id": "I999999999", "vin": vin(999999999)}[field]
    elif issue == "invalid_state":
        row["state"] = "XX"
    elif issue == "invalid_opened_date":
        row["opened_date"] = "2018-02-30"
    elif issue == "invalid_active_status":
        row["active_status"] = "unknown"
    elif issue == "whitespace_name":
        field = "dealer_name" if table == "dealers" else "full_name"
        row[field] = "  " + row[field] + "  "
    elif issue in {"negative_mileage", "nonnumeric_mileage"}:
        row["mileage"] = "-500" if issue == "negative_mileage" else "unknown"
    elif issue == "future_year":
        row["year"] = "2099"
    elif issue == "invalid_acquired_date":
        row["acquired_date"] = "2025-02-30"
    elif issue == "whitespace_vin":
        row["vin"] = " " + row["vin"] + " "
    elif issue == "dealer_mismatch":
        row["dealer_id"] = "D002" if row["dealer_id"] == "D001" else "D001"
    elif issue in {"negative_price", "nonnumeric_price", "currency_formatted_price"}:
        field = "list_price" if table == "listings" else "sale_price"
        row[field] = {"negative_price": "-500.00", "nonnumeric_price": "TBD", "currency_formatted_price": f"${float(row[field]):,.2f}"}[issue]
    elif issue == "listing_before_acquisition":
        row["listed_date"] = DATES[context["acquired_day"] - 7]
    elif issue == "invalid_listing_status":
        row["listing_status"] = "maybe"
    elif issue == "invalid_email":
        row["email"] = "not-an-email"
    elif issue == "invalid_phone":
        row["phone_number"] = "12AB"
    elif issue == "future_created_date":
        row["created_date"] = "2035-01-01"
    elif issue == "email_case_and_spaces":
        row["email"] = " " + row["email"].upper() + " "
    elif issue == "formatted_phone":
        digits = row["phone_number"][2:]
        row["phone_number"] = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif issue == "inquiry_before_listing":
        row["inquiry_date"] = DATES[context["listed_day"] - 2] + "T10:00:00"
    elif issue == "invalid_inquiry_date":
        row["inquiry_date"] = "2025-13-40T25:61:00"
    elif issue == "invalid_inquiry_status":
        row["inquiry_status"] = "pending_forever"
    elif issue == "invalid_channel":
        row["inquiry_channel"] = "carrier_pigeon"
    elif issue == "whitespace_customer_id":
        row["customer_id"] = " " + row["customer_id"] + " "
    elif issue == "sale_before_inquiry":
        row["sale_date"] = DATES[context["inquiry_day"] - 1]
    elif issue == "sale_customer_mismatch":
        row["customer_id"] = identifier("C", 2 if row["customer_id"] == identifier("C", 1) else 1)
    elif issue == "sale_vehicle_mismatch":
        row["vin"] = vin(2 if row["vin"] == vin(1) else 1)
    elif issue == "future_sale_date":
        row["sale_date"] = "2035-01-01"
    else:
        raise ValueError(issue)
    return [row[field] for field in SCHEMAS[table]]


class Sink:
    """Stream raw CSV and a separate, row-addressed mutation ledger."""

    def __init__(self, stack, output, table, ledger, seed, dirty):
        self.table, self.ledger, self.seed, self.dirty = table, ledger, seed, dirty
        self.file = stack.enter_context((output / "raw" / f"{table}.csv").open("w", encoding="utf-8", newline="", buffering=1024 * 1024))
        self.writer = csv.writer(self.file, lineterminator="\n")
        self.writer.writerow(SCHEMAS[table])
        self.clean_hash = hashlib.sha256(csv_line(SCHEMAS[table]).encode())
        self.clean_buffer = io.StringIO(newline="")
        self.clean_writer = csv.writer(self.clean_buffer, lineterminator="\n")
        self.clean_rows = self.raw_rows = self.issue_index = 0
        self.issue_counts = Counter()

    def flush_hash(self):
        self.clean_hash.update(self.clean_buffer.getvalue().encode())
        self.clean_buffer.seek(0)
        self.clean_buffer.truncate(0)

    def emit(self, source, context=None):
        source = [str(value) for value in source]
        self.clean_rows += 1
        self.clean_writer.writerow(source)
        if self.clean_rows % 10000 == 0:
            self.flush_hash()
        # Do not alter the three introductory dealership rows. Guarantee every
        # issue type appears early, then introduce issues in ~2% of base rows.
        n = self.clean_rows
        eligible = not (self.table == "dealers" and n <= 3)
        first_example = 4 <= n < 4 + len(ISSUES[self.table])
        inject = self.dirty and eligible and (first_example or mix(n, self.seed + len(self.table)) % 50 == 0)
        if not inject:
            self.writer.writerow(source)
            self.raw_rows += 1
            return
        issue = ISSUES[self.table][self.issue_index % len(ISSUES[self.table])]
        self.issue_index += 1
        altered = changed_row(self.table, source, issue, context or {})
        duplicate = issue.startswith("duplicate_")
        if duplicate:
            self.writer.writerow(source)
            self.raw_rows += 1
        self.writer.writerow(altered)
        self.raw_rows += 1
        self.issue_counts[issue] += 1
        self.ledger.writerow([
            self.table + ".csv", self.raw_rows, source[0], issue,
            "drop_inserted_duplicate" if duplicate else "restore_original",
            "normalize" if issue in NORMALIZABLE else "review",
            json.dumps(source, separators=(",", ":")),
            json.dumps(altered, separators=(",", ":")),
        ])

    def finish(self):
        self.flush_hash()
        self.file.flush()
        return {"base_rows": self.clean_rows, "raw_rows": self.raw_rows,
                "injected_rows": sum(self.issue_counts.values()),
                "issues": dict(sorted(self.issue_counts.items())),
                "clean_sha256": self.clean_hash.hexdigest()}


def generate(output, preset, seed, dirty):
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite nonempty directory: {output}")
    config = PRESETS[preset]
    output.mkdir(parents=True, exist_ok=True)
    (output / "raw").mkdir()
    (output / "answer_key").mkdir()
    active_dealers = [i for i in range(1, config["dealers"] + 1) if not inactive(i)]
    with ExitStack() as stack:
        ledger_file = stack.enter_context((output / "answer_key" / "injected_issues.csv").open("w", encoding="utf-8", newline="", buffering=1024 * 1024))
        ledger = csv.writer(ledger_file, lineterminator="\n")
        ledger.writerow(["file", "data_row_number", "original_key", "issue_type", "reconstruction_action", "handling_hint", "original_row_json", "dirty_row_json"])
        sinks = {table: Sink(stack, output, table, ledger, seed, dirty) for table in SCHEMAS}
        initial = [
            ["D001", "Carmel Auto Center", "Carmel", "IN", "2014-05-12", "active"],
            ["D002", "Indy Motor Group", "Indianapolis", "IN", "2011-08-23", "active"],
            ["D003", "Fishers Premier Autos", "Fishers", "IN", "2018-03-07", "inactive"],
        ]
        for n in range(1, config["dealers"] + 1):
            h = mix(n, seed)
            city, state, _ = MARKETS[h % len(MARKETS)]
            row = initial[n - 1] if n <= 3 else [dealer_id(n), f"{city} Motor Group {n:04d}", city, state, f"{2000 + h % 19}-03-07", "inactive" if inactive(n) else "active"]
            sinks["dealers"].emit(row)
        print(f"Dealers generated: {config['dealers']:,}", flush=True)
        for n in range(1, config["customers"] + 1):
            h = mix(n, seed + 1)
            city, state, area = MARKETS[h % len(MARKETS)]
            name = FIRST[h % len(FIRST)] + " " + LAST[(h // 29) % len(LAST)]
            sinks["customers"].emit([identifier("C", n), name, f"customer{n:09d}@example.com", f"+1{area}555{100 + h % 100:04d}", city, DATES[h % 730]])
            if n % 500000 == 0:
                print(f"Customers generated: {n:,}", flush=True)
        inquiry_n = listing_n = 0
        sale_count = unsold_count = 0
        for n in range(1, config["vehicles"] + 1):
            h = mix(n, seed + 2)
            h2 = mix(n, seed + 3)
            sold = n % 100 not in UNSOLD_POSITIONS
            dealer_n = 1 + h % config["dealers"]
            if not sold:
                dealer_n = active_dealers[h % len(active_dealers)]
            if sold:
                upper = (date(2022, 11, 1) - EPOCH).days if inactive(dealer_n) else END_SOLD_DAY
                acquired_day = START_DAY + h2 % (upper - START_DAY + 1)
            else:
                acquired_day = AS_OF_DAY - (35 + h2 % 145)
            year = int(DATES[acquired_day][:4]) - h % 12
            make, model, base_price = CARS[(h // 17) % len(CARS)]
            mileage = (int(DATES[acquired_day][:4]) - year) * 10500 + h2 % 17000
            list_cents = max(3500, base_price - (int(DATES[acquired_day][:4]) - year) * 1700 - mileage // 30 + h % 3000) * 100
            vehicle_vin, owning_dealer = vin(n), dealer_id(dealer_n)
            sinks["vehicles"].emit([vehicle_vin, owning_dealer, year, make, model, mileage, DATES[acquired_day]])
            first_day = acquired_day + 1 + h % 7
            relisted = n % 5 == 0
            listing_n += 1
            first_listing = identifier("L", listing_n)
            sinks["listings"].emit([first_listing, vehicle_vin, owning_dealer, money(list_cents), DATES[first_day], "withdrawn" if relisted else ("sold" if sold else "active")], {"acquired_day": acquired_day})
            current_listing, current_day = first_listing, first_day
            if relisted:
                listing_n += 1
                current_listing, current_day = identifier("L", listing_n), first_day + 14
                list_cents -= 50000
                sinks["listings"].emit([current_listing, vehicle_vin, owning_dealer, money(list_cents), DATES[current_day], "sold" if sold else "active"], {"acquired_day": acquired_day})
            inquiry_count = INQUIRY_COUNTS[(n - 1) % 10]
            for j in range(inquiry_count):
                inquiry_n += 1
                # First and final inquiries can be the same customer's separate
                # contact events. Different inquiry IDs must not be collapsed.
                customer_n = 1 + ((n - 1 + (0 if j in {0, inquiry_count - 1} else j * 7919)) % config["customers"])
                customer = identifier("C", customer_n)
                inquiry_id = identifier("I", inquiry_n)
                on_old_listing = relisted and inquiry_count > 1 and j == 0
                linked_listing = first_listing if on_old_listing else current_listing
                listed_day = first_day if on_old_listing else current_day
                inquiry_day = listed_day + 1 + j * 2
                status = "converted" if sold and j == inquiry_count - 1 else ("closed_lost" if sold or on_old_listing else ["new", "contacted", "qualified", "closed_lost"][(h + j) % 4])
                timestamp = DATES[inquiry_day] + f"T{9 + (h + j) % 10:02d}:{h2 % 60:02d}:00"
                sinks["inquiries"].emit([inquiry_id, customer, linked_listing, ["web_form", "phone", "email", "walk_in"][(h + j) % 4], timestamp, status], {"listed_day": listed_day})
            if sold:
                sale_day = inquiry_day + 1 + h % 14
                discount_cents = list_cents * (h2 % 1101) // 10000
                sinks["sales"].emit([identifier("S", n), vehicle_vin, customer, inquiry_id, money(list_cents - discount_cents), DATES[sale_day]], {"inquiry_day": inquiry_day})
                sale_count += 1
            else:
                unsold_count += 1
            if n % 250000 == 0:
                print(f"Vehicle histories generated: {n:,} / {config['vehicles']:,}", flush=True)
        files = {table + ".csv": sink.finish() for table, sink in sinks.items()}
    for name, stats in files.items():
        path = output / "raw" / name
        stats["bytes"] = path.stat().st_size
        with path.open("rb") as stream:
            stats["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {
        "generator_version": VERSION, "preset": preset, "seed": seed,
        "as_of_date": AS_OF.isoformat(), "synthetic": True,
        "dirty": dirty, "files": files,
        "base_controls": {"sold_vehicles": sale_count, "unsold_vehicles": unsold_count,
                          "converted_inquiries": sale_count, "vehicles_with_second_listing": config["vehicles"] // 5},
        "total_base_rows": sum(s["base_rows"] for s in files.values()),
        "total_raw_rows": sum(s["raw_rows"] for s in files.values()),
        "total_injected_rows": sum(s["injected_rows"] for s in files.values()),
        "total_csv_bytes": sum(s["bytes"] for s in files.values()),
        "note": "Injected row count is not the number of downstream validation failures. Broken parent keys can affect many children. See docs/SYNTHETIC_DATA.md.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Complete: {manifest['total_raw_rows']:,} rows; {manifest['total_injected_rows']:,} injected rows", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New or empty dataset directory")
    parser.add_argument("--preset", choices=PRESETS, default="practice")
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--clean", action="store_true", help="Omit deliberate defects; same underlying records")
    args = parser.parse_args()
    generate(args.output, args.preset, args.seed, not args.clean)


if __name__ == "__main__":
    main()
