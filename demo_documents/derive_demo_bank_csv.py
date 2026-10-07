"""Create the structured demo bank import from the existing synthetic PDF."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "02_bank_statement.pdf"
DESTINATION = ROOT / "02_bank_statement.csv"
TRANSACTION = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)

text = "\n".join(page.get_text() for page in pymupdf.open(SOURCE))
rows = [match.groups() for line in text.splitlines() if (match := TRANSACTION.match(line.strip()))]
if len(rows) != 84:
    raise SystemExit(f"Expected 84 existing synthetic transactions; parsed {len(rows)}.")

with DESTINATION.open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(("Date", "Description", "Debit", "Credit", "Balance"))
    writer.writerows(rows)

print(f"Wrote {len(rows)} transactions from {SOURCE.name} to {DESTINATION.name}.")
