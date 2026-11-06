import csv
import sys

with open(sys.argv[1], newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
for col in rows[0] if rows else []:
    empty = sum(1 for r in rows if not r[col])
    print(f"{col}: {empty}/{len(rows)} empty")
