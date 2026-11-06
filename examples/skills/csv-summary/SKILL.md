---
name: csv-summary
description: Summarise a CSV file - column types, missing values and a few example rows. Use when the user shares a CSV or asks what is in a spreadsheet export.
license: MIT
allowed-tools: Bash(python:*) Read
---

# CSV summary

1. Run `scripts/summarise.py <file.csv>` and read its output.
2. Report the column list with inferred types, the share of empty cells per column, and
   three representative rows.
3. If a column looks like personal data (emails, phone numbers), say so and don't print
   its values.

See [the column type rules](references/types.md) for how types are inferred.
