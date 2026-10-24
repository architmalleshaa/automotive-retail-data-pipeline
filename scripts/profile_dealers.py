import csv
from pathlib import Path

file_path = Path("data/raw/dealers.csv")
print(file_path.exists())  # show whether the CSV exists

with file_path.open(mode="r", encoding="utf-8", newline="") as csv_file:
    reader = csv.DictReader(csv_file)
    print(reader.fieldnames)  # show the column names

    row_count = 0
    dealer_ids = set()  # remember non-blank IDs from earlier rows
    saved_rows={}
    missing_dealer_id_count = 0
    repeated_id_count=0
    matching_first_row_count=0
    different_first_row_count=0

    for dealer_record in reader:                 # get the next CSV row
        dealer_id = dealer_record["dealer_id"]   # take THIS row's ID
        row_count = row_count + 1                # count THIS row

        if dealer_id == "":                      # is THIS row's ID blank?
            missing_dealer_id_count = missing_dealer_id_count + 1
        else:                                    # this row has an ID
            if dealer_id in dealer_ids:          # did an earlier row have this ID?
                print("Repeated dealer_id:", dealer_id)
                repeated_id_count=repeated_id_count+1

                earlier_row=saved_rows[dealer_id]
                print("Rows identical:",dealer_record==earlier_row)

                if dealer_record==earlier_row:
                    matching_first_row_count=matching_first_row_count+1
                else:
                     different_first_row_count=different_first_row_count+1
            else:
                saved_rows[dealer_id]=dealer_record
            dealer_ids.add(dealer_id)            # remember it for later rows

    print("Total rows:", row_count)
    print("Rows missing dealer_id:", missing_dealer_id_count)
    print("Different dealer_id values:", len(dealer_ids))
    print("Repeated dealer_id rows:",repeated_id_count)
    print("Repeated rows matching first row:", matching_first_row_count)
    print("Repeated rows differing from first row:", different_first_row_count)
