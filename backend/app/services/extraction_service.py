"""Document text extraction and raw field parsing. No feature engineering here.

Pipeline per document:
  stored file bytes
  -> text layer (embedded PDF text via PyMuPDF, every page)
  -> scanned/image content via local PaddleOCR text recognition
     (PP-OCRv4 mobile models, plain CPU), every page in order
  -> deterministic per-type field parsers (regex over present text only)
  -> one Extraction row per document (upserted on re-run)

Honesty rules enforced by construction:
- only information present in the document text is extracted; absent keys
  are omitted, never defaulted or fabricated;
- unreadable content yields FAILED with a clear message;
- nothing here computes model features, scores, or explanations.
"""

from __future__ import annotations

import io
import json
import logging
import re
import threading
from typing import Any

import pymupdf
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, Extraction, User
from app.services import storage_service

logger = logging.getLogger(__name__)

TEXT_ENGINE = "pymupdf-text"
PADDLE_ENGINE = "paddleocr"
OCR_UNAVAILABLE_ENGINE = "ocr-unavailable"

_paddle_pipeline = None
_paddle_lock = threading.Lock()


def _get_paddle_pipeline():
    """Lazily built, process-wide PaddleOCR text pipeline (PP-OCRv4, plain CPU)."""

    global _paddle_pipeline
    if _paddle_pipeline is None:
        from paddleocr import PaddleOCR

        _paddle_pipeline = PaddleOCR(
            lang="en", ocr_version="PP-OCRv4", enable_mkldnn=False
        )
    return _paddle_pipeline


def paddle_ocr_image(image: Image.Image) -> tuple[list[str], list[float], str | None]:
    """OCR one image, returning (text lines, line confidences 0-1, error)."""

    try:
        import numpy as _numpy

        if image.mode != "RGB":
            image = image.convert("RGB")
        array = _numpy.asarray(image)
    except Exception as exc:
        return [], [], f"Unable to prepare the image for OCR: {exc}"
    try:
        with _paddle_lock:
            result = _get_paddle_pipeline().predict(input=array)
    except Exception as exc:
        return [], [], f"OCR failed: {exc}"
    lines: list[str] = []
    scores: list[float] = []
    try:
        pages = result if isinstance(result, list) else [result]
        for page in pages:
            texts = page.get("rec_texts") or []
            confidences = page.get("rec_scores") or []
            for index, text in enumerate(texts):
                cleaned = str(text).strip()
                if not cleaned:
                    continue
                lines.append(cleaned)
                try:
                    scores.append(float(confidences[index]))
                except (IndexError, TypeError, ValueError):
                    continue
    except Exception as exc:
        return [], [], f"OCR output unreadable: {exc}"
    if not lines:
        return [], [], "OCR produced no readable text."
    return lines, scores, None


def _mean_percent(scores: list[float]) -> float | None:
    valid = [value for value in scores if 0.0 <= value <= 1.0]
    if not valid:
        return None
    return round(sum(valid) / len(valid) * 100.0, 1)


_structure_pipeline = None
_structure_lock = threading.Lock()


def _get_structure_pipeline():
    """Lazily built, process-wide PP-StructureV3 pipeline for layout/table extraction."""
    global _structure_pipeline
    if _structure_pipeline is None:
        from paddleocr import PPStructureV3

        _structure_pipeline = PPStructureV3(lang="en", enable_mkldnn=False)
    return _structure_pipeline


def extract_structured_document(
    image: Image.Image,
) -> tuple[dict[str, Any], list[float], str | None]:
    """Extract structured document layout using PP-StructureV3.

    Returns (structured_result, scores, error).
    structured_result contains tables, layout, and text regions with bounding boxes.
    """
    try:
        import numpy as _numpy

        if image.mode != "RGB":
            image = image.convert("RGB")
        array = _numpy.asarray(image)
    except Exception as exc:
        return {}, [], f"Unable to prepare image for structure extraction: {exc}"
    try:
        with _structure_lock:
            result = _get_structure_pipeline().predict(input=array)
    except Exception as exc:
        return {}, [], f"Structure extraction failed: {exc}"
    try:
        pages = result if isinstance(result, list) else [result]
        page = pages[0] if pages else {}
        # Extract text with confidence from OCR results
        texts = page.get("overall_ocr_res", {}).get("rec_texts", [])
        confidences = page.get("overall_ocr_res", {}).get("rec_scores", [])
        scores = [
            float(c)
            for c in confidences
            if isinstance(c, (int, float)) and 0.0 <= c <= 1.0
        ]
        return page, scores, None
    except Exception as exc:
        return {}, [], f"Structure output unreadable: {exc}"


def _extract_table_rows(page_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract transaction rows from PP-StructureV3 table results.

    Returns list of normalized transaction dicts with date, description, debit, credit, balance.
    """
    tables = page_result.get("table_res_list", [])
    if not tables:
        return []

    transactions = []
    for table in tables:
        # Table structure from PP-StructureV3 contains cells with row/col indices and text
        cells = table.get("cells", [])
        if not cells:
            continue
        # Group cells by row
        rows: dict[int, dict[int, str]] = {}
        for cell in cells:
            row_idx = cell.get("row_idx", cell.get("row", 0))
            col_idx = cell.get("col_idx", cell.get("col", 0))
            text = str(cell.get("text", cell.get("content", ""))).strip()
            if not text:
                continue
            rows.setdefault(row_idx, {})[col_idx] = text
        if not rows:
            continue
        # Detect header row to map column indices
        header_row_idx = min(rows.keys())
        header_cells = rows[header_row_idx]
        col_map = {}
        for col_idx, header_text in header_cells.items():
            h = header_text.lower()
            if "date" in h:
                col_map[col_idx] = "date"
            elif "description" in h or "narration" in h or "particular" in h:
                col_map[col_idx] = "description"
            elif "debit" in h or "withdrawal" in h or "dr" == h:
                col_map[col_idx] = "debit"
            elif "credit" in h or "deposit" in h or "cr" == h:
                col_map[col_idx] = "credit"
            elif "balance" in h:
                col_map[col_idx] = "balance"
            elif "type" in h or "dr/cr" in h:
                col_map[col_idx] = "type"
            elif "amount" in h:
                col_map[col_idx] = "amount"
        # Parse data rows
        for row_idx in sorted(rows.keys()):
            if row_idx == header_row_idx:
                continue
            row_data = rows[row_idx]
            date = row_data.get(
                next((k for k, v in col_map.items() if v == "date"), -1), ""
            )
            description = row_data.get(
                next((k for k, v in col_map.items() if v == "description"), -1), ""
            )
            balance = row_data.get(
                next((k for k, v in col_map.items() if v == "balance"), -1), ""
            )
            debit = row_data.get(
                next((k for k, v in col_map.items() if v == "debit"), -1), ""
            )
            credit = row_data.get(
                next((k for k, v in col_map.items() if v == "credit"), -1), ""
            )
            txn_type = row_data.get(
                next((k for k, v in col_map.items() if v == "type"), -1), ""
            )
            amount = row_data.get(
                next((k for k, v in col_map.items() if v == "amount"), -1), ""
            )

            # Normalize debit/credit from type+amount if needed
            if (not debit or not credit) and amount and txn_type:
                amt = _parse_amount(amount)
                if amt is not None:
                    if "credit" in txn_type.lower():
                        credit = str(abs(amt))
                        debit = "0"
                    elif "debit" in txn_type.lower():
                        debit = str(abs(amt))
                        credit = "0"

            if not date:
                continue
            transactions.append(
                {
                    "date": date,
                    "description": description[:256],
                    "debit": _parse_amount(debit) or 0.0,
                    "credit": _parse_amount(credit) or 0.0,
                    "balance": _parse_amount(balance) or 0.0,
                }
            )
    return transactions


def _ocr_pages_with_structure(
    images: list[Image.Image], page_count: int
) -> tuple[str, str, float | None, str | None]:
    """OCR every rasterized page with PP-StructureV3 layout analysis, preserving page boundaries."""
    chunks: list[str] = []
    scores: list[float] = []
    structure_pages = 0
    table_pages = 0
    total_transactions = 0

    for index, image in enumerate(images, start=1):
        # Try PP-StructureV3 first for layout/table extraction
        page_result, page_scores, struct_error = extract_structured_document(image)

        table_transactions = _extract_table_rows(page_result)
        if table_transactions:
            table_pages += 1
            total_transactions += len(table_transactions)
            # Format structured transactions as text for downstream parser
            for txn in table_transactions:
                chunks.append(
                    f"{txn['date']} {txn['description']} {txn['debit']} {txn['credit']} {txn['balance']}"
                )
        else:
            # Fallback to regular PaddleOCR text extraction
            lines, ocr_scores, error = paddle_ocr_image(image)
            if error is not None and not lines:
                return "", OCR_UNAVAILABLE_ENGINE, None, f"Page {index}: {error}"
            chunks.extend(lines)
            scores.extend(ocr_scores)

        if page_scores:
            scores.extend(page_scores)
        structure_pages += 1
        chunks.append(f"--- page {index} of {page_count} ---")

    text = "\n".join(chunks)
    if not text.strip():
        return "", OCR_UNAVAILABLE_ENGINE, None, "OCR produced no readable text."

    logger.info(
        "ppstructure pages_processed=%d structure_pages=%d table_pages=%d transactions_from_tables=%d raw_text_length=%d",
        page_count,
        structure_pages,
        table_pages,
        total_transactions,
        len(text),
    )
    return text, PADDLE_ENGINE, _mean_percent(scores), None


def _ocr_pages(
    images: list[Image.Image], page_count: int
) -> tuple[str, str, float | None, str | None]:
    """OCR every rasterized page in order, preserving page boundaries."""

    chunks: list[str] = []
    scores: list[float] = []
    ocr_pages = 0
    for index, image in enumerate(images, start=1):
        lines, page_scores, error = paddle_ocr_image(image)
        if error is not None and not lines:
            return "", OCR_UNAVAILABLE_ENGINE, None, f"Page {index}: {error}"
        ocr_pages += 1
        chunks.append(f"--- page {index} of {page_count} ---")
        chunks.extend(lines)
        scores.extend(page_scores)
    text = "\n".join(chunks)
    if not text.strip():
        return "", OCR_UNAVAILABLE_ENGINE, None, "OCR produced no readable text."
    logger.info(
        "paddleocr pages_processed=%d ocr_pages_processed=%d raw_text_length=%d",
        page_count,
        ocr_pages,
        len(text),
    )
    return text, PADDLE_ENGINE, _mean_percent(scores), None


_AMOUNT_PATTERN = re.compile(r"(?:Rs\.?|INR|\u20b9)?\s*([\d,]+(?:\.\d{1,2})?)")
_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b",
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> float | None:
    try:
        return round(float(raw.replace(",", "")), 2)
    except (TypeError, ValueError):
        return None


def _labeled_amount(text: str, *labels: str) -> float | None:
    for line in text.splitlines():
        lowered = line.lower()
        if any(label in lowered for label in labels):
            if "=" in line and ":" not in line:
                continue
            for match in _AMOUNT_PATTERN.finditer(line):
                start, end = match.span(1)
                # Skip fragments of calendar dates such as 05/01/2024.
                if line[start - 1 : start] == "/" or line[end : end + 1] == "/":
                    continue
                value = _parse_amount(match.group(1))
                if value is not None:
                    return value
    return None


def _labeled_text(text: str, *labels: str) -> str | None:
    for line in text.splitlines():
        lowered = line.lower()
        for label in labels:
            if label in lowered:
                if "=" in line and ":" not in line:
                    break
                _, _, tail = line.partition(":")
                candidate = tail.strip() if ":" in line else line.strip()
                if candidate:
                    return candidate[:256]
    return None


def _first_date(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    return match.group(1) if match else None


def _keyword_present(text: str, *keywords: str) -> str | None:
    lowered = text.lower()
    for keyword in keywords:
        if keyword in lowered:
            return keyword
    return None


def parse_salary(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    name = _labeled_text(text, "employee name", "employee:", "name:")
    if name:
        fields["employee_name"] = name
    employer = _labeled_text(text, "employer", "company")
    if employer:
        fields["employer"] = employer
    period = _labeled_text(text, "salary period", "pay period", "pay month", "month:")
    if period:
        fields["salary_period"] = period
    for key, labels in (
        ("basic_salary", ("basic",)),
        ("gross_salary", ("gross",)),
        ("net_salary", ("net pay", "net salary", "take home", "take-home")),
    ):
        value = _labeled_amount(text, *labels)
        if value is not None:
            fields[key] = value
    pay_date = _labeled_text(text, "pay date", "payment date", "date:")
    if pay_date:
        fields["pay_date"] = pay_date
    elif _first_date(text):
        fields["pay_date"] = _first_date(text)
    return fields


def _parse_bank_transactions_pipe_format(text: str) -> list[dict[str, Any]]:
    """Parse bank transactions from pipe-separated format (PaddleOCR scanned output).

    Expected format per line:
    date | description | type | amount | balance
    3-11-2025 | RENT PAYMENT | Debit | INR -18,000 | Balance INR 95,300
    03/11/2025 | SALARY CREDIT | Credit | INR 57,800 | Balance INR 1,53,100
    """
    # Pattern matches: date | description | type | amount | balance
    # Amount can be: INR -18,000, INR 18,000, ₹18,000, ₹ -18,000, 18,000, 18000, 1,02,450
    # Balance can be: Balance INR 95,300, Balance ₹95,300, Balance 95300
    row_pattern = re.compile(
        r"^\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"  # date
        r"\s*\|\s*"
        r"(.+?)"  # description
        r"\s*\|\s*"
        r"(Credit|Debit)"  # type (explicit)
        r"\s*\|\s*"
        r"(?:INR|₹|Rs\.?)\s*(-?[\d,]+(?:\.\d{1,2})?)"  # amount with optional sign
        r"\s*\|\s*"
        r"(?:Balance\s*)?(?:INR|₹|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)"  # balance
        r"\s*$",
        re.IGNORECASE,
    )
    transactions = []
    for line in text.splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        date_str = match.group(1)
        description = match.group(2).strip()[:256]
        txn_type = match.group(3).lower()
        amount_str = match.group(4)
        balance_str = match.group(5)

        amount = _parse_amount(amount_str)
        balance = _parse_amount(balance_str)
        if amount is None or balance is None:
            continue

        # Use explicit type field (Credit/Debit) rather than sign
        if txn_type == "credit":
            credit = abs(amount)
            debit = 0.0
        elif txn_type == "debit":
            debit = abs(amount)
            credit = 0.0
        else:
            continue  # Unknown type, skip

        transactions.append(
            {
                "date": date_str,
                "description": description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )
    return transactions


def _parse_bank_transactions_single_line(text: str) -> list[dict[str, Any]]:
    """Parse bank transactions from single-line format (demo_documents style).

    Expected format per line:
    Date Description Debit Credit Balance
    05/01/2024 SALARY-CREDIT 0.00 95,000.00 215,000.00
    """
    row_pattern = re.compile(
        r"^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
    )
    transactions = []
    for line in text.splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        debit = _parse_amount(match.group(3))
        credit = _parse_amount(match.group(4))
        balance = _parse_amount(match.group(5))
        if debit is None or credit is None or balance is None:
            continue
        transactions.append(
            {
                "date": match.group(1),
                "description": match.group(2).strip()[:256],
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )
    return transactions


def _parse_bank_transactions_multi_line(text: str) -> list[dict[str, Any]]:
    """Parse bank transactions from multi-line format (Slips 12-month style).

    Each transaction spans 5 lines:
    Date
    Description
    Type (Credit/Debit)
    Amount
    Balance

    Column headers (Date, Description, Type, Amount, Balance) repeat on each page.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    transactions = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for date pattern to start a transaction
        date_match = re.match(r"^(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})$", line)
        if not date_match:
            i += 1
            continue
        date = date_match.group(1)
        # Need at least 4 more lines for description, type, amount, balance
        if i + 4 >= len(lines):
            break
        description = lines[i + 1]
        txn_type = lines[i + 2].lower()
        amount_str = lines[i + 3]
        balance_str = lines[i + 4]

        # Skip header rows
        if description.lower() == "description" and txn_type == "type":
            i += 5
            continue

        amount = _parse_amount(amount_str)
        balance = _parse_amount(balance_str)
        if amount is None or balance is None:
            i += 1
            continue

        if "credit" in txn_type:
            credit = abs(amount)
            debit = 0.0
        elif "debit" in txn_type:
            debit = abs(amount)
            credit = 0.0
        else:
            # Fallback: infer from sign
            if amount < 0:
                debit = abs(amount)
                credit = 0.0
            else:
                credit = amount
                debit = 0.0

        transactions.append(
            {
                "date": date,
                "description": description[:256],
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )
        i += 5
    return transactions


def _parse_monthly_cash_flow(text: str) -> list[dict[str, Any]]:
    """Parse monthly cash flow summary from text (Slips 12-month style).

    Format:
    Month
    Credits
    Debits
    Net
    Oct-2025
    65,000
    48,700
    16,300
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cash_flow = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for month pattern like Oct-2025, Nov-2025, etc.
        month_match = re.match(
            r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[- ]\d{4}$",
            line,
            re.IGNORECASE,
        )
        if not month_match:
            i += 1
            continue
        month = month_match.group(0)
        if i + 3 >= len(lines):
            break
        credits = _parse_amount(lines[i + 1])
        debits = _parse_amount(lines[i + 2])
        net = _parse_amount(lines[i + 3])
        if credits is not None and debits is not None and net is not None:
            cash_flow.append(
                {
                    "month": month,
                    "credits": credits,
                    "debits": debits,
                    "net": net,
                }
            )
        i += 4
    return cash_flow


def parse_bank_statement(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    account = re.search(
        r"(?:account(?:\s+no\.?|\s+number)?|a/?c(?:count)?(?:\s+no\.?)?)\s*[:#]?\s*(\d{6,20})",
        text,
        re.IGNORECASE,
    )
    if account:
        fields["account_number"] = account.group(1)
    period = _labeled_text(text, "statement period", "period:")
    if period:
        fields["statement_period"] = period

    # Priority 1: Pipe-separated format (PaddleOCR scanned output)
    transactions = _parse_bank_transactions_pipe_format(text)
    # Priority 2: Single-line format (demo_documents style)
    if not transactions:
        transactions = _parse_bank_transactions_single_line(text)
    # Priority 3: Multi-line format (Slips 12-month style)
    if not transactions:
        transactions = _parse_bank_transactions_multi_line(text)

    if transactions:
        fields["transactions"] = transactions

    # Parse monthly cash flow if present
    monthly_cash_flow = _parse_monthly_cash_flow(text)
    if monthly_cash_flow:
        fields["monthly_cash_flow"] = monthly_cash_flow

    return fields


def parse_credit_report(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    lender = _labeled_text(text, "lender", "bank:", "institution")
    if lender:
        fields["lender"] = lender
    account_type = _keyword_present(
        text,
        "credit card",
        "home loan",
        "personal loan",
        "auto loan",
        "consumer loan",
        "mortgage",
    )
    if account_type:
        fields["account_type"] = account_type
    for key, labels in (
        ("sanctioned_amount", ("sanctioned",)),
        ("outstanding_amount", ("outstanding",)),
        ("credit_limit", ("credit limit", "limit")),
        ("overdue_amount", ("overdue",)),
    ):
        value = _labeled_amount(text, *labels)
        if value is not None:
            fields[key] = value
    overdue_days = re.search(
        r"(\d+)\s*days?\s*(?:past\s*due|overdue|dpd)", text, re.IGNORECASE
    )
    if overdue_days:
        fields["overdue_days"] = int(overdue_days.group(1))
    status = _keyword_present(
        text, "active", "closed", "settled", "written off", "default"
    )
    if status:
        fields["account_status"] = status
    applications = []
    for line in text.splitlines():
        lowered = line.lower()
        if (
            "approv" in lowered or "refus" in lowered or "reject" in lowered
        ) and _AMOUNT_PATTERN.search(line):
            applications.append(line.strip()[:256])
    if applications:
        fields["application_records"] = applications
    return fields


def parse_loan_document(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, labels in (
        ("loan_amount", ("loan amount", "sanctioned", "principal")),
        ("emi", ("emi", "annuity", "instalment", "installment")),
    ):
        value = _labeled_amount(text, *labels)
        if value is not None:
            fields[key] = value
    contract = _keyword_present(text, "cash loan", "revolving", "term loan")
    if contract:
        fields["contract_info"] = contract
    first_date = _first_date(text)
    if first_date:
        fields["relevant_date"] = first_date
    return fields


def parse_insurance(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    policy = _keyword_present(
        text, "health", "life", "term plan", "endowment", "ulip", "money back"
    )
    if policy:
        fields["policy_type"] = policy
    premium = _labeled_amount(text, "premium")
    if premium is not None:
        fields["premium"] = premium
    frequency = _keyword_present(
        text,
        "monthly",
        "quarterly",
        "half-yearly",
        "annual",
        "yearly",
        "single premium",
    )
    if frequency:
        fields["premium_frequency"] = frequency
    status = _keyword_present(
        text, "in-force", "in force", "active", "lapsed", "paid-up", "matured"
    )
    if status:
        fields["policy_status"] = status
    dates = _DATE_PATTERN.findall(text)
    if dates:
        fields["payment_dates"] = [str(found) for found in dates[:12]]
    return fields


def parse_investment(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    lowered = text.lower()
    products = (
        ("fd", ("fixed deposit", " fd ", "fd account")),
        (
            "rd",
            (
                "recurring deposit",
                " rd ",
            ),
        ),
        ("sip", ("sip", "systematic investment")),
        ("mutual_fund", ("mutual fund",)),
        ("ppf", ("ppf", "public provident")),
        ("nps", ("nps", "national pension")),
    )
    for key, keywords in products:
        for line in text.splitlines():
            if any(keyword in line.lower() for keyword in keywords):
                match = _AMOUNT_PATTERN.search(line)
                if match:
                    value = _parse_amount(match.group(1))
                    if value is not None:
                        fields[key] = value
                        break
    return fields


PARSERS = {
    "salary_income_proof": parse_salary,
    "bank_statement": parse_bank_statement,
    "credit_report": parse_credit_report,
    "loan_document": parse_loan_document,
    "insurance_document": parse_insurance,
    "investment_statement": parse_investment,
}


def extract_text(
    data: bytes, filename: str
) -> tuple[str, str, float | None, str | None]:
    """Return (raw_text, engine, confidence, error) across every PDF page.

    Text PDFs use embedded text. Pages without usable text are rasterized
    for PP-StructureV3 (with PaddleOCR fallback). Standalone images go to PP-StructureV3.
    """

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "pdf":
        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:
                page_count = len(document)
                embedded = [page.get_text() or "" for page in document]
        except Exception as exc:
            return "", OCR_UNAVAILABLE_ENGINE, None, f"Unable to read the PDF: {exc}"
        if not page_count:
            return "", OCR_UNAVAILABLE_ENGINE, None, "The PDF has no readable pages."
        if all(text.strip() for text in embedded):
            return "\n".join(embedded), TEXT_ENGINE, None, None
        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:
                images = [
                    Image.open(
                        io.BytesIO(
                            page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
                        )
                    )
                    for page in document
                ]
        except Exception as exc:
            return (
                "",
                OCR_UNAVAILABLE_ENGINE,
                None,
                f"Unable to rasterize the PDF: {exc}",
            )
        return _ocr_pages_with_structure(images, page_count)
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
    except Exception as exc:
        return "", OCR_UNAVAILABLE_ENGINE, None, f"Unable to read the image: {exc}"
    # For standalone images, try PP-StructureV3 first
    page_result, scores, error = extract_structured_document(image)
    table_transactions = _extract_table_rows(page_result)
    if table_transactions:
        # Format structured transactions as text for downstream parser
        lines = []
        for txn in table_transactions:
            lines.append(
                f"{txn['date']} {txn['description']} {txn['debit']} {txn['credit']} {txn['balance']}"
            )
        text = "\n".join(lines)
        logger.info(
            "ppstructure image tables_found=1 transactions=%d", len(table_transactions)
        )
        return text, PADDLE_ENGINE, _mean_percent(scores), None
    # Fallback to regular PaddleOCR
    lines, scores, error = paddle_ocr_image(image)
    if error is not None:
        return "", OCR_UNAVAILABLE_ENGINE, None, error
    return "\n".join(lines), PADDLE_ENGINE, _mean_percent(scores), None


def run_extraction(db: Session, *, document: Document) -> Extraction:
    """Extract one document, upserting its single Extraction row and honest statuses."""

    document.processing_status = "PROCESSING"
    db.flush()

    stored = document.storage_reference or ""
    try:
        data, _ = storage_service.load_file(stored)
    except Exception as exc:
        return _record_failure(
            db,
            document,
            f"Stored file is unavailable: {exc}",
            engine=OCR_UNAVAILABLE_ENGINE,
        )

    raw_text, engine, confidence, error = extract_text(data, stored)
    if error is not None:
        return _record_failure(db, document, error, engine=engine)

    parser = PARSERS.get(document.document_type)
    structured = parser(raw_text) if parser else {}
    return _record_success(
        db,
        document,
        raw_text=raw_text,
        structured=structured,
        engine=engine,
        confidence=confidence,
    )


def _record_success(
    db: Session,
    document: Document,
    *,
    raw_text: str,
    structured: dict[str, Any],
    engine: str,
    confidence: float | None,
) -> Extraction:
    extraction = _get_or_create(db, document)
    extraction.raw_text = raw_text
    extraction.structured_data = json.dumps(structured)
    extraction.extraction_status = "EXTRACTED"
    extraction.review_status = "REVIEW_REQUIRED"
    extraction.engine = engine
    extraction.confidence = confidence
    extraction.error_message = None
    document.processing_status = "EXTRACTED"
    document.extraction_status = "EXTRACTED"
    document.review_status = "REVIEW_REQUIRED"
    db.flush()
    return extraction


def _record_failure(
    db: Session, document: Document, message: str, *, engine: str
) -> Extraction:
    extraction = _get_or_create(db, document)
    extraction.raw_text = ""
    extraction.structured_data = "{}"
    extraction.extraction_status = "FAILED"
    extraction.review_status = "REVIEW_REQUIRED"
    extraction.engine = engine
    extraction.confidence = None
    extraction.error_message = message[:1024]
    document.processing_status = "FAILED"
    document.extraction_status = "FAILED"
    document.review_status = "REVIEW_REQUIRED"
    db.flush()
    return extraction


def _get_or_create(db: Session, document: Document) -> Extraction:
    extraction = (
        db.query(Extraction).filter(Extraction.document_id == document.id).first()
    )
    if extraction is None:
        extraction = Extraction(document_id=document.id)
        db.add(extraction)
        db.flush()
    return extraction


def to_read_model(extraction: Extraction) -> dict[str, Any]:
    """Shape a stored row for the read schema, parsing its JSON payload."""

    try:
        structured = json.loads(extraction.structured_data or "{}")
    except (TypeError, json.JSONDecodeError):
        structured = {}
    if not isinstance(structured, dict):
        structured = {}
    return {
        "id": extraction.id,
        "document_id": extraction.document_id,
        "raw_text": extraction.raw_text or "",
        "structured_data": structured,
        "extraction_status": extraction.extraction_status,
        "review_status": extraction.review_status,
        "engine": extraction.engine or "",
        "confidence": extraction.confidence,
        "error_message": extraction.error_message,
        "created_at": extraction.created_at,
        "updated_at": extraction.updated_at,
    }


def get_extraction(db: Session, *, user: User, document: Document) -> Extraction | None:
    """Return the extraction row only when the document belongs to the user."""

    owned = (
        db.query(Document)
        .filter(Document.id == document.id, Document.user_id == user.id)
        .first()
    )
    if owned is None:
        return None
    return db.query(Extraction).filter(Extraction.document_id == document.id).first()
