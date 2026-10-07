"""Bank transaction import and normalization service.

Supports CSV, XLSX, and TXT formats with flexible header detection.
Normalizes to canonical transaction schema for FRIE feature derivation.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from app.services.extraction_service import _parse_amount as _parse_amount_extraction

# Column header aliases for flexible mapping
DATE_ALIASES = {
    "date",
    "transaction date",
    "txn date",
    "value date",
    "posting date",
    "transaction_date",
    "txn_date",
    "value_date",
    "posting_date",
}
DESCRIPTION_ALIASES = {
    "description",
    "narration",
    "remarks",
    "particulars",
    "details",
    "transaction details",
    "transaction_details",
}
DEBIT_ALIASES = {
    "debit",
    "withdrawal",
    "dr",
    "debit amount",
    "withdrawal amount",
    "debit_amt",
    "withdrawal_amt",
}
CREDIT_ALIASES = {
    "credit",
    "deposit",
    "cr",
    "credit amount",
    "deposit amount",
    "credit_amt",
    "deposit_amt",
}
BALANCE_ALIASES = {
    "balance",
    "closing balance",
    "running balance",
    "available balance",
    "closing_balance",
    "running_balance",
    "available_balance",
}
AMOUNT_ALIASES = {
    "amount",
    "transaction amount",
    "txn amount",
    "amt",
    "transaction_amt",
    "txn_amt",
}
TYPE_ALIASES = {
    "type",
    "txn type",
    "transaction type",
    "dr/cr",
    "debit/credit",
    "txn_type",
    "transaction_type",
}


@dataclass
class BankTransaction:
    """Canonical bank transaction after normalization."""

    transaction_date: date
    description: str
    transaction_type: str  # "credit" or "debit"
    credit_amount: float | None
    debit_amount: float | None
    balance: float | None
    source_row: int  # original row number for error reporting


@dataclass
class ImportResult:
    """Result of bank statement import."""

    transactions: list[BankTransaction]
    warnings: list[str]
    errors: list[str]
    detected_format: str
    date_range: tuple[date, date] | None
    total_credits: float
    total_debits: float
    row_count: int


def _normalize_header(header: str) -> str:
    """Normalize column header for matching."""
    return re.sub(r"[\s_/-]+", " ", header.strip().lower())


def _detect_delimiter(sample: str) -> str:
    """Detect delimiter from sample text."""
    if "\t" in sample:
        return "\t"
    if "|" in sample:
        return "|"
    if "," in sample:
        return ","
    return None


def _parse_date_flexible(date_str: str) -> date | None:
    """Parse date with multiple format support."""
    if not date_str or pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m.%d.%Y",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y.%m.%d",
        "%d/%m/%y",
        "%d-%m-%y",
        "%m/%d/%y",
        "%m-%d-%y",
        "%Y/%m/%d",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    # Try pandas flexible parsing as last resort
    try:
        return pd.to_datetime(date_str, dayfirst=True).date()
    except Exception:
        pass
    return None


def _parse_amount_flexible(amount_str: str) -> float | None:
    """Parse amount with support for INR, ₹, commas, negatives."""
    if not amount_str or pd.isna(amount_str):
        return None
    # Use the existing extraction parser which handles INR/₹/commas
    return _parse_amount_extraction(str(amount_str))


def _detect_format_and_columns(df: pd.DataFrame) -> tuple[str, dict[str, str]]:
    """Detect bank statement format and map columns to canonical names."""
    normalized_cols = {_normalize_header(c): c for c in df.columns}

    # Check for separate debit/credit columns
    has_debit = any(alias in normalized_cols for alias in DEBIT_ALIASES)
    has_credit = any(alias in normalized_cols for alias in CREDIT_ALIASES)
    has_amount = any(alias in normalized_cols for alias in AMOUNT_ALIASES)
    has_type = any(alias in normalized_cols for alias in TYPE_ALIASES)

    if has_debit and has_credit:
        format_type = "separate_debit_credit"
    elif has_amount and has_type:
        format_type = "signed_amount_with_type"
    elif has_amount:
        format_type = "signed_amount"
    else:
        format_type = "unknown"

    # Map columns
    col_map = {}
    for canonical, aliases in [
        ("date", DATE_ALIASES),
        ("description", DESCRIPTION_ALIASES),
        ("debit", DEBIT_ALIASES),
        ("credit", CREDIT_ALIASES),
        ("balance", BALANCE_ALIASES),
        ("amount", AMOUNT_ALIASES),
        ("type", TYPE_ALIASES),
    ]:
        for alias in aliases:
            if alias in normalized_cols:
                col_map[canonical] = normalized_cols[alias]
                break

    return format_type, col_map


def _normalize_transactions(
    df: pd.DataFrame, format_type: str, col_map: dict[str, str]
) -> tuple[list[BankTransaction], list[str], list[str]]:
    """Normalize dataframe rows to canonical BankTransaction objects."""
    transactions = []
    warnings = []
    errors = []

    date_col = col_map.get("date")
    desc_col = col_map.get("description")
    debit_col = col_map.get("debit")
    credit_col = col_map.get("credit")
    balance_col = col_map.get("balance")
    amount_col = col_map.get("amount")
    type_col = col_map.get("type")

    if not date_col:
        errors.append("No date column detected")
        return [], warnings, errors
    if not desc_col:
        errors.append("No description/narration column detected")
        return [], warnings, errors

    seen_transactions = set()  # for duplicate detection

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-based, accounting for header

        # Parse date
        txn_date = _parse_date_flexible(row[date_col])
        if txn_date is None:
            errors.append(f"Row {row_num}: Invalid or missing date '{row[date_col]}'")
            continue

        # Parse description
        description = str(row[desc_col]).strip() if not pd.isna(row[desc_col]) else ""
        if not description:
            warnings.append(f"Row {row_num}: Empty description")
            description = "UNKNOWN"

        # Parse amounts based on format
        debit_amount = None
        credit_amount = None
        balance = None
        txn_type = None

        if format_type == "separate_debit_credit":
            if debit_col and not pd.isna(row[debit_col]):
                debit_amount = _parse_amount_flexible(row[debit_col])
            if credit_col and not pd.isna(row[credit_col]):
                credit_amount = _parse_amount_flexible(row[credit_col])
            # Determine type from which column has value
            if debit_amount is not None and debit_amount > 0:
                txn_type = "debit"
            elif credit_amount is not None and credit_amount > 0:
                txn_type = "credit"
            else:
                warnings.append(
                    f"Row {row_num}: Both debit and credit are zero or missing"
                )

        elif format_type == "signed_amount_with_type":
            amount = (
                _parse_amount_flexible(row[amount_col])
                if amount_col and not pd.isna(row[amount_col])
                else None
            )
            txn_type_raw = (
                str(row[type_col]).strip().lower()
                if type_col and not pd.isna(row[type_col])
                else ""
            )

            if amount is not None:
                if "credit" in txn_type_raw or "cr" == txn_type_raw:
                    credit_amount = abs(amount)
                    txn_type = "credit"
                elif "debit" in txn_type_raw or "dr" == txn_type_raw or amount < 0:
                    debit_amount = abs(amount)
                    txn_type = "debit"
                else:
                    credit_amount = amount
                    txn_type = "credit"

        elif format_type == "signed_amount":
            amount = (
                _parse_amount_flexible(row[amount_col])
                if amount_col and not pd.isna(row[amount_col])
                else None
            )
            if amount is not None:
                if amount < 0:
                    debit_amount = abs(amount)
                    txn_type = "debit"
                else:
                    credit_amount = amount
                    txn_type = "credit"

        else:
            errors.append(
                f"Row {row_num}: Unsupported format, cannot determine debit/credit"
            )
            continue

        # Parse balance
        if balance_col and not pd.isna(row[balance_col]):
            balance = _parse_amount_flexible(row[balance_col])

        # Duplicate detection (same date, description, amount)
        txn_key = (
            txn_date.isoformat(),
            description,
            debit_amount or 0,
            credit_amount or 0,
        )
        if txn_key in seen_transactions:
            warnings.append(f"Row {row_num}: Potential duplicate transaction")
        seen_transactions.add(txn_key)

        if txn_type is None:
            errors.append(f"Row {row_num}: Could not determine transaction type")
            continue

        transactions.append(
            BankTransaction(
                transaction_date=txn_date,
                description=description[:256],
                transaction_type=txn_type,
                credit_amount=credit_amount,
                debit_amount=debit_amount,
                balance=balance,
                source_row=row_num,
            )
        )

    return transactions, warnings, errors


def import_bank_statement(file_data: bytes, filename: str) -> ImportResult:
    """Import bank statement from CSV, XLSX, or TXT file."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        if extension == "csv":
            # Try different encodings and delimiters
            for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    df = pd.read_csv(io.BytesIO(file_data), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                df = pd.read_csv(
                    io.BytesIO(file_data), encoding="utf-8", encoding_errors="replace"
                )

        elif extension in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(file_data))

        elif extension == "txt":
            # Try to detect delimiter
            sample = file_data[:8192].decode("utf-8", errors="replace")
            delimiter = _detect_delimiter(sample)
            if delimiter:
                df = pd.read_csv(io.BytesIO(file_data), delimiter=delimiter)
            else:
                # Try fixed width or space-separated
                df = pd.read_csv(io.BytesIO(file_data), sep=r"\s+", engine="python")

        else:
            return ImportResult(
                transactions=[],
                warnings=[],
                errors=[f"Unsupported file format: {extension}"],
                detected_format="unknown",
                date_range=None,
                total_credits=0.0,
                total_debits=0.0,
                row_count=0,
            )

    except Exception as exc:
        return ImportResult(
            transactions=[],
            warnings=[],
            errors=[f"Failed to parse file: {exc}"],
            detected_format="unknown",
            date_range=None,
            total_credits=0.0,
            total_debits=0.0,
            row_count=0,
        )

    if df.empty:
        return ImportResult(
            transactions=[],
            warnings=["File contains no data rows"],
            errors=[],
            detected_format="empty",
            date_range=None,
            total_credits=0.0,
            total_debits=0.0,
            row_count=0,
        )

    # Detect format and map columns
    format_type, col_map = _detect_format_and_columns(df)

    if format_type == "unknown":
        return ImportResult(
            transactions=[],
            warnings=[],
            errors=[
                "Could not detect bank statement format. Expected columns for date, description, and amounts."
            ],
            detected_format="unknown",
            date_range=None,
            total_credits=0.0,
            total_debits=0.0,
            row_count=len(df),
        )

    # Normalize transactions
    transactions, warnings, errors = _normalize_transactions(df, format_type, col_map)

    # Calculate totals and date range
    total_credits = sum(t.credit_amount or 0 for t in transactions)
    total_debits = sum(t.debit_amount or 0 for t in transactions)

    dates = [t.transaction_date for t in transactions]
    date_range = (min(dates), max(dates)) if dates else None

    # Sort by date
    transactions.sort(key=lambda t: t.transaction_date)

    return ImportResult(
        transactions=transactions,
        warnings=warnings,
        errors=errors,
        detected_format=format_type,
        date_range=date_range,
        total_credits=total_credits,
        total_debits=total_debits,
        row_count=len(df),
    )


def transactions_to_dataframe(transactions: list[BankTransaction]) -> pd.DataFrame:
    """Convert normalized transactions to DataFrame for feature derivation."""
    if not transactions:
        return pd.DataFrame(
            columns=["date", "description", "debit", "credit", "balance"]
        )

    rows = []
    for t in transactions:
        rows.append(
            {
                "date": t.transaction_date,
                "description": t.description,
                "debit": t.debit_amount or 0.0,
                "credit": t.credit_amount or 0.0,
                "balance": t.balance,
            }
        )
    return pd.DataFrame(rows)


def derive_monthly_features(
    transactions: list[BankTransaction],
) -> dict[str, float | int]:
    """Derive FRIE monthly features from normalized transactions.

    Returns monthly aggregated features matching the FRIE feature contract.
    """
    if not transactions:
        return {}

    df = transactions_to_dataframe(transactions)
    df["month"] = df["date"].apply(lambda d: f"{d.month:02d}/{d.year}")

    # Categorize transactions
    EXPENSE_KEYWORDS = {
        "food_expense": (
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
        "rent_expense": ("rent", "landlord", "house rent", "flat rent"),
        "education_expense": (
            "school",
            "college",
            "tuition",
            "education",
            "fees",
            "university",
            "course",
        ),
        "healthcare_expense": (
            "hospital",
            "clinic",
            "pharmacy",
            "medical",
            "health",
            "diagnostic",
            "doctor",
        ),
        "transport_expense": (
            "uber",
            "ola",
            "fuel",
            "petrol",
            "metro",
            "transport",
            "taxi",
            "cab",
            "railway",
        ),
        "utility_expense": (
            "electricity",
            "water bill",
            "gas bill",
            "mobile recharge",
            "recharge",
            "broadband",
            "utility",
            "dth",
        ),
        "discretionary_expense": (
            "shopping",
            "mall",
            "amazon",
            "flipkart",
            "entertainment",
            "movie",
            "salon",
            "gym",
            "travel",
            "flight",
        ),
    }
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

    monthly_data = {}
    for _, row in df.iterrows():
        month = row["month"]
        debit = row["debit"]
        credit = row["credit"]
        desc = str(row["description"]).lower()

        if month not in monthly_data:
            monthly_data[month] = {
                "upi_sum": 0.0,
                "upi_count": 0,
                "net": 0.0,
                "food_expense": 0.0,
                "rent_expense": 0.0,
                "education_expense": 0.0,
                "healthcare_expense": 0.0,
                "transport_expense": 0.0,
                "utility_expense": 0.0,
                "discretionary_expense": 0.0,
            }

        bucket = monthly_data[month]
        bucket["net"] += credit - debit

        if debit > 0:
            if any(kw in desc for kw in TRANSFER_KEYWORDS):
                continue  # Skip transfers/investments

            categorized = False
            for category, keywords in EXPENSE_KEYWORDS.items():
                if any(kw in desc for kw in keywords):
                    bucket[category] += debit
                    categorized = True
                    break

            if any(kw in desc for kw in UPI_KEYWORDS):
                bucket["upi_sum"] += debit
                bucket["upi_count"] += 1

    months = sorted(monthly_data.keys())
    if len(months) < 12:
        # Not enough months for reliable cash flow stats
        return {}

    # Calculate averages
    result = {}
    for category in [
        "food_expense",
        "rent_expense",
        "education_expense",
        "healthcare_expense",
        "transport_expense",
        "utility_expense",
        "discretionary_expense",
    ]:
        values = [monthly_data[m].get(category, 0.0) for m in months]
        result[category] = round(sum(values) / len(values), 2)

    upi_sums = [monthly_data[m]["upi_sum"] for m in months]
    upi_counts = [monthly_data[m]["upi_count"] for m in months]
    result["upi_spending"] = round(sum(upi_sums) / len(upi_sums), 2)
    result["upi_transaction_count"] = int(round(sum(upi_counts) / len(upi_counts)))

    nets = [monthly_data[m]["net"] for m in months]
    result["monthly_savings"] = round(max(sum(nets) / len(nets), 0.0), 2)

    import statistics

    result["cash_flow_mean"] = round(sum(nets) / len(nets), 2)
    result["cash_flow_std"] = (
        round(statistics.pstdev(nets), 2) if len(nets) > 1 else 0.0
    )
    result["cash_flow_min"] = round(min(nets), 2)
    result["cash_flow_negative_months"] = sum(1 for net in nets if net < 0)

    # Latest balance
    balances = [t.balance for t in transactions if t.balance is not None]
    if balances:
        result["savings_balance"] = round(float(balances[-1]), 2)

    return result
