"""Strict parsing of structured credit-history record lines from raw document text.

Demo credit reports carry machine-readable record lines alongside human
text. Only lines matching the documented shapes below are accepted; anything
else is ignored (never guessed). Required keys per record kind are enforced;
incomplete records are skipped, never defaulted.

Shapes (pipe-separated key=value pairs):
  TRADELINE | lender=.. | type=.. | limit=.. | balance=.. | debt=..
              | overdue=.. | dpd=.. | prolong=.. | status=..
  INSTALLMENT | date=DD/MM/YYYY | paid_date=DD/MM/YYYY | due=.. | paid=..
              (paid_date optional; without it, payment-timing features stay missing)
  PREVAPP | status=Approved|Refused|.. | credit=.. | annuity=.. | down=.. | goods=..
  CARDMONTH | balance=.. | limit=.. | drawings=.. | payments=.. | minimum=..
              | dpd=.. | dpd_default=..
  POSREC | installments=.. | future=.. | dpd=.. | dpd_default=..
"""

from __future__ import annotations

import re
from datetime import datetime

_DATE_PATTERN = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_int(raw: str | None) -> int | None:
    value = _parse_number(raw)
    if value is None or not float(value).is_integer():
        return None
    return int(value)


def _parse_fields(line: str) -> dict[str, str]:
    parts = [segment.strip() for segment in line.split("|")]
    fields: dict[str, str] = {}
    for segment in parts[1:]:
        if "=" not in segment:
            return {}
        key, _, value = segment.partition("=")
        key, value = key.strip().lower(), value.strip()
        if not key or not value:
            return {}
        fields[key] = value
    return fields


def parse_credit_records(text: str) -> dict[str, list[dict]]:
    """Parse structured credit records. Unknown lines are ignored."""

    records: dict[str, list[dict]] = {
        "tradelines": [],
        "installments": [],
        "previous_applications": [],
        "card_months": [],
        "pos_records": [],
    }
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        head, _, _ = line.partition("|")
        kind = head.strip().upper()
        if kind == "TRADELINE":
            fields = _parse_fields(line)
            debt = _parse_number(fields.get("debt"))
            if debt is None:
                continue
            records["tradelines"].append(
                {
                    "lender": fields.get("lender", ""),
                    "type": fields.get("type", ""),
                    "limit": _parse_number(fields.get("limit")) or 0.0,
                    "balance": _parse_number(fields.get("balance")) or 0.0,
                    "debt": debt,
                    "overdue": _parse_number(fields.get("overdue")) or 0.0,
                    "dpd": _parse_int(fields.get("dpd")) or 0,
                    "prolong": _parse_int(fields.get("prolong")) or 0,
                    "status": fields.get("status", ""),
                }
            )
        elif kind == "INSTALLMENT":
            fields = _parse_fields(line)
            due = _parse_number(fields.get("due"))
            paid = _parse_number(fields.get("paid"))
            if due is None or paid is None or not _DATE_PATTERN.match(fields.get("date", "")):
                continue
            paid_date = fields.get("paid_date", "")
            records["installments"].append(
                {
                    "date": fields["date"],
                    "paid_date": paid_date if _DATE_PATTERN.match(paid_date) else "",
                    "due": due,
                    "paid": paid,
                }
            )
        elif kind == "PREVAPP":
            fields = _parse_fields(line)
            credit = _parse_number(fields.get("credit"))
            if not fields.get("status") or credit is None:
                continue
            records["previous_applications"].append(
                {
                    "status": fields["status"],
                    "credit": credit,
                    "annuity": _parse_number(fields.get("annuity")) or 0.0,
                    "down": _parse_number(fields.get("down")) or 0.0,
                    "goods": _parse_number(fields.get("goods")) or 0.0,
                }
            )
        elif kind == "CARDMONTH":
            fields = _parse_fields(line)
            balance = _parse_number(fields.get("balance"))
            limit = _parse_number(fields.get("limit"))
            if balance is None or limit is None:
                continue
            records["card_months"].append(
                {
                    "balance": balance,
                    "limit": limit,
                    "drawings": _parse_number(fields.get("drawings")) or 0.0,
                    "payments": _parse_number(fields.get("payments")) or 0.0,
                    "minimum": _parse_number(fields.get("minimum")) or 0.0,
                    "dpd": _parse_int(fields.get("dpd")) or 0,
                    "dpd_default": _parse_int(fields.get("dpd_default")) or 0,
                }
            )
        elif kind == "POSREC":
            fields = _parse_fields(line)
            installments = _parse_int(fields.get("installments"))
            future = _parse_int(fields.get("future"))
            if installments is None or future is None:
                continue
            records["pos_records"].append(
                {
                    "installments": installments,
                    "future": future,
                    "dpd": _parse_int(fields.get("dpd")) or 0,
                    "dpd_default": _parse_int(fields.get("dpd_default")) or 0,
                }
            )
    return records


def parse_iso_date(raw: str | None) -> str | None:
    """Validate an ISO calendar date string, returning None when unparseable."""

    if not raw:
        return None
    try:
        datetime.strptime(raw.strip(), "%Y-%m-%d")
        return raw.strip()
    except ValueError:
        return None
