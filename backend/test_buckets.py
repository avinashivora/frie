from collections import defaultdict
from datetime import datetime

from app.services.extraction_service import parse_bank_statement
from app.services.transaction_classifier import classify_transactions

text = """FAKE DEMO BANK STATEMENT - SYNTHETIC DATA ONLY
Account No: 987654321098
05/01/2024 SALARY-CREDIT 0.00 95,000.00 215,000.00
08/01/2024 UPI-BIGBASKET-GROCERY 3,000.00 0.00 212,000.00
11/01/2024 UPI-SWIGGY-FOOD 2,500.00 0.00 209,500.00
14/01/2024 ELECTRICITY-BILL-NEFT 1,500.00 0.00 208,000.00
15/01/2024 HOUSE-Rent-NEFT 18,000.00 0.00 190,000.00
18/01/2024 OLA-CAB-RIDE 1,200.00 0.00 188,800.00
22/01/2024 SIP-HDFC-MUTUALFUND 5,000.00 0.00 183,800.00"""

result = parse_bank_statement(text)
transactions = result.get("transactions", [])

txns_for_classification = []
for txn in transactions:
    debit = txn.get("debit", 0.0)
    credit = txn.get("credit", 0.0)
    if debit > 0:
        txn_type = "debit"
    elif credit > 0:
        txn_type = "credit"
    else:
        continue
    txns_for_classification.append(
        {
            "description": txn.get("description", ""),
            "transaction_type": txn_type,
            "debit_amount": debit,
            "credit_amount": credit,
            "balance": txn.get("balance"),
            "transaction_date": txn.get("date"),
        }
    )

from app.services.transaction_classifier import classify_transactions

classified = classify_transactions(txns_for_classification)

EXPENSE_KEYWORDS = (
    (
        "food_expense",
        (
            "swiggy",
            "zomato",
            "restaurant",
            "food",
            "grocery",
            "supermarket",
            "bigbasket",
            "dominos",
            "cafe",
            "dining",
        ),
    ),
    ("rent_expense", ("rent", "landlord", "house rent", "flat rent")),
)
UPI_KEYWORDS = ("upi",)
TRANSFER_KEYWORDS = (
    "sip",
    "mutual",
    "fixed deposit",
    "recurring deposit",
    "ppf",
    "nps",
    "investment",
    "transfer",
)

monthly_buckets = defaultdict(
    lambda: {
        "upi_sum": 0.0,
        "upi_count": 0,
        "net": 0.0,
        "food_expense": 0.0,
        "rent_expense": 0.0,
    }
)

for cls in classified:
    debit = cls.amount if cls.transaction_type == "debit" else 0.0
    credit = cls.amount if cls.transaction_type == "credit" else 0.0

    txn_date = None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            txn_date = datetime.strptime(cls.date, fmt).date()
            break
        except (ValueError, AttributeError):
            continue

    if txn_date is None:
        print("FAILED to parse date for", cls.description, cls.date)
        continue

    month_key = f"{txn_date.month:02d}/{txn_date.year}"
    debit = cls.amount if cls.transaction_type == "debit" else 0.0
    credit = cls.amount if cls.transaction_type == "credit" else 0.0

    bucket = monthly_buckets[f"{txn_date.month:02d}/{txn_date.year}"]
    bucket["net"] += credit - debit
    if debit > 0:
        lowered = cls.description.lower()
        if any(
            kw in lowered
            for kw in (
                "sip",
                "mutual",
                "fixed deposit",
                "recurring deposit",
                "ppf",
                "nps",
                "investment",
                "transfer",
            )
        ):
            print("  SKIPPED", cls.description, "(transfer)")
            continue
        for category, keywords in (
            (
                "food_expense",
                (
                    "swiggy",
                    "zomato",
                    "restaurant",
                    "food",
                    "grocery",
                    "supermarket",
                    "bigbasket",
                    "dominos",
                    "cafe",
                    "dining",
                ),
            ),
            ("rent_expense", ("rent", "landlord", "house rent", "flat rent")),
        ):
            if any(kw in cls.description.lower() for kw in keywords[1]):
                print("  CATEGORIZED", cls.description, "as", category)
                bucket[category] += debit
                break
        if any(kw in cls.description.lower() for kw in ("upi",)):
            bucket["upi_sum"] += debit
            bucket["upi_count"] += 1

print("Monthly buckets:")
for month, bucket in monthly_buckets.items():
    print(
        f"  {month}: food={bucket['food_expense']}, rent={bucket['rent_expense']}, net={bucket['net']}"
    )
