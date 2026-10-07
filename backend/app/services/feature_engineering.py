"""Phase 6 feature engineering: USER + DOCUMENT + confirmed states -> exact 98 features.

Rules enforced here (see docs/FRIE_98_FEATURE_PROVENANCE.md for formulas):
- Only documented derivations; no new formulas, no renamed features.
- Confirmed NONE yields deterministic values only where feature semantics
  allow (counts/amounts of absent products); ratios over empty denominators
  stay missing (matching the research NaN semantics) instead of invented.
- UNKNOWN / never-answered / unreviewed sources yield missing, never zeros.
- DOCUMENT-provenance values require a REVIEWED extraction.
- Nothing here calls the model, scores, or explains.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Document, Extraction, FinancialFeature, FinancialStatus, User
from app.schemas.profile import CATEGORICAL_LEVELS
from app.services import credit_records
from app.services.bank_import import derive_monthly_features
from app.services.transaction_classifier import (
    ClassifiedTransaction,
    classify_transactions,
)

# Full model-level categorical sets. The ten profile fields mirror the
# fitted encoder exactly (see the parity test); city_tier uses the Census
# tiers and occupation_band the four PLFS bands. Note the fitted V2
# encoder only ever saw a subset of occupation bands, so Self_Employed and
# Casual_Worker pass validation here but contribute nothing until a model
# trained on those levels exists. That limitation is documented, not hidden.
MODEL_CATEGORICAL_LEVELS: dict[str, tuple[str, ...]] = {
    **CATEGORICAL_LEVELS,
    "city_tier": ("Tier_1", "Tier_2", "Tier_3"),
    "occupation_band": ("Other", "Salaried", "Self_Employed", "Casual_Worker"),
}

# Prototype city-tier mapping (documented; unknown cities stay missing).
TIER_1_CITIES = {
    "mumbai",
    "delhi",
    "new delhi",
    "bengaluru",
    "bangalore",
    "chennai",
    "hyderabad",
    "kolkata",
    "ahmedabad",
    "pune",
}
TIER_2_CITIES = {
    "jaipur",
    "lucknow",
    "kanpur",
    "nagpur",
    "indore",
    "thane",
    "bhopal",
    "visakhapatnam",
    "patna",
    "vadodara",
    "surat",
    "coimbatore",
    "kochi",
    "chandigarh",
    "ludhiana",
    "agra",
    "nashik",
    "faridabad",
    "meerut",
    "rajkot",
    "varanasi",
    "aurangabad",
    "amritsar",
    "prayagraj",
    "allahabad",
    "ranchi",
    "jabalpur",
    "gwalior",
    "vijayawada",
    "jodhpur",
    "madurai",
    "raipur",
    "kota",
    "guwahati",
    "thiruvananthapuram",
    "mysuru",
    "mysore",
    "tiruchirappalli",
    "bareilly",
    "jalandhar",
    "bhubaneswar",
    "dehradun",
    "udaipur",
    "puducherry",
    "pondicherry",
}

EXPENSE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
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
    (
        "education_expense",
        ("school", "college", "tuition", "education", "fees", "university", "course"),
    ),
    (
        "healthcare_expense",
        ("hospital", "clinic", "pharmacy", "medical", "health", "diagnostic", "doctor"),
    ),
    (
        "transport_expense",
        (
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
    ),
    (
        "utility_expense",
        (
            "electricity",
            "water bill",
            "gas bill",
            "mobile recharge",
            "recharge",
            "broadband",
            "utility",
            "dth",
        ),
    ),
    (
        "discretionary_expense",
        (
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
    ),
)
UPI_KEYWORDS = ("upi",)
# Recognized investment/transfer outflows: counted in cash nets but never
# classified as consumption expenses and never treated as uncategorized.
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

CASH_MIN_MONTHS = 12


def employment_band(income_type: Any, occupation: Any) -> str | None:
    """Exact research rule from 02_generate_indian_synthetic.py::employment_class."""

    value = f"{income_type} {occupation}".lower()
    if "business" in value:
        return "Self_Employed"
    if "working" in value or "state servant" in value or "government" in value:
        return "Salaried"
    if "labour" in value:
        return "Casual_Worker"
    return "Other"


def city_tier(city: Any) -> str | None:
    """Documented prototype Census-tier lookup; unknown cities stay missing."""

    if not isinstance(city, str) or not city.strip():
        return None
    normalized = city.strip().lower()
    if normalized in TIER_1_CITIES:
        return "Tier_1"
    if normalized in TIER_2_CITIES:
        return "Tier_2"
    return None


def _years_between(start: date, today: date) -> float:
    return (today - start).days / 365.25


class Assembly:
    """Accumulates one user's feature attempt with provenance and reasons."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.provenance: dict[str, str] = {}
        self.sources: dict[str, int | None] = {}
        self.status: dict[str, str] = {}  # READY, UNKNOWN, VERIFIED, USER_CONFIRMED
        self.missing: list[dict[str, str]] = []
        self.confidence: dict[str, float] = {}

    def put(
        self,
        name: str,
        value: Any,
        provenance: str,
        source_document_id: int | None = None,
        status: str = "READY",
        confidence: float = 1.0,
    ) -> None:
        self.values[name] = value
        self.provenance[name] = provenance
        self.sources[name] = source_document_id
        self.status[name] = status
        self.confidence[name] = confidence
        self.missing = [entry for entry in self.missing if entry["feature"] != name]

    def miss(self, name: str, reason: str, block: str) -> None:
        if not any(entry["feature"] == name for entry in self.missing):
            self.missing.append({"feature": name, "reason": reason, "block": block})
            self.status[name] = "UNKNOWN"


def _reviewed_extractions(
    db: Session, user: User
) -> dict[str, tuple[Document, Extraction]]:
    """Latest REVIEWED extraction per document type for the user."""

    out: dict[str, tuple[Document, Extraction]] = {}
    rows = (
        db.query(Document, Extraction)
        .join(Extraction, Extraction.document_id == Document.id)
        .filter(Document.user_id == user.id, Extraction.review_status == "REVIEWED")
        .order_by(Document.id.desc())
        .all()
    )
    for document, extraction in rows:
        out.setdefault(document.document_type, (document, extraction))
    return out


def _profile_value(profile: Any, name: str) -> Any:
    return getattr(profile, name, None) if profile is not None else None


def _valid_level(value: Any, levels: tuple[str, ...]) -> bool:
    return isinstance(value, str) and value in levels


def assemble(db: Session, user: User) -> Assembly:
    """Build the 98-feature attempt from profile, declarations, and reviewed extractions."""

    from app.db.models import CustomerProfile
    from app.services import profile_service  # noqa: PLC0415 (avoid import cycle at module load)

    assembly = Assembly()
    profile = profile_service.get_profile(db, user=user)
    status_row = (
        db.query(FinancialStatus).filter(FinancialStatus.user_id == user.id).first()
    )
    reviewed = _reviewed_extractions(db, user)
    today = date.today()

    def need_profile(name: str, value: Any, check) -> Any:
        if not check(value):
            assembly.miss(name, "profile field missing or invalid", "profile")
            return None
        return value

    # ---- Direct USER pass-through (levels enforced) ----
    for name in (
        "gender",
        "children_count",
        "family_size",
        "family_status",
        "education_level",
        "housing_type",
        "owns_car",
        "owns_property",
        "income_type",
        "occupation",
        "organization_type",
        "contract_type",
    ):
        value = _profile_value(profile, name)
        if name in CATEGORICAL_LEVELS:
            if _valid_level(value, CATEGORICAL_LEVELS[name]):
                assembly.put(name, value, "USER")
            else:
                assembly.miss(name, "profile field missing or invalid", "profile")
        elif isinstance(value, bool) or value is None or not isfinite(float(value)):
            assembly.miss(name, "profile field missing or invalid", "profile")
        else:
            assembly.put(name, value, "USER")

    income = _profile_value(profile, "monthly_income")
    if (
        isinstance(income, bool)
        or income is None
        or not isfinite(float(income))
        or float(income) <= 0
    ):
        assembly.miss("monthly_income", "profile field missing or invalid", "profile")
        income = None
    else:
        assembly.put("monthly_income", float(income), "USER")

    dob = _profile_value(profile, "date_of_birth")
    if isinstance(dob, date) and dob <= today and (today - dob).days <= 120 * 365.25:
        assembly.put("age_years", round((today - dob).days / 365.25, 2), "USER")
    else:
        assembly.miss("age_years", "profile field missing or invalid", "profile")

    start = _profile_value(profile, "employment_start")
    if isinstance(start, date) and start <= today:
        assembly.put(
            "employment_years", round((today - start).days / 365.25, 2), "USER"
        )
    else:
        assembly.miss("employment_years", "profile field missing or invalid", "profile")

    tier = city_tier(_profile_value(profile, "city"))
    if tier is None:
        city = _profile_value(profile, "city")
        assembly.miss("city_tier", f"city tier unmapped for {city!r}", "profile")
    else:
        assembly.put("city_tier", tier, "USER")

    occupation = _profile_value(profile, "occupation")
    income_type = _profile_value(profile, "income_type")
    if _valid_level(occupation, CATEGORICAL_LEVELS["occupation"]) and _valid_level(
        income_type, CATEGORICAL_LEVELS["income_type"]
    ):
        assembly.put(
            "occupation_band", employment_band(income_type, occupation), "USER"
        )
    else:
        assembly.miss("occupation_band", "profile field missing or invalid", "profile")

    family_size = _profile_value(profile, "family_size")
    if (
        isinstance(family_size, bool)
        or family_size is None
        or not isfinite(float(family_size))
    ):
        assembly.miss(
            "indian_household_size", "profile field missing or invalid", "profile"
        )
    else:
        assembly.put("indian_household_size", int(family_size), "USER")

    declarations = {
        "has_loan": getattr(status_row, "has_loan", None),
        "insurance_status": getattr(status_row, "insurance_status", None),
        "inv_fd": getattr(status_row, "inv_fd", None),
        "inv_rd": getattr(status_row, "inv_rd", None),
        "inv_sip": getattr(status_row, "inv_sip", None),
        "inv_mutual_fund": getattr(status_row, "inv_mutual_fund", None),
        "inv_ppf": getattr(status_row, "inv_ppf", None),
        "inv_nps": getattr(status_row, "inv_nps", None),
    }

    bank = reviewed.get("bank_statement")
    bank_import = reviewed.get("bank_import")
    salary = reviewed.get("salary_income_proof")
    credit = reviewed.get("credit_report")
    loan = reviewed.get("loan_document")
    insurance = reviewed.get("insurance_document")
    investment = reviewed.get("investment_statement")

    _bank_block(assembly, bank, bank_import)
    _credit_block(assembly, credit, declarations)
    _loan_block(assembly, loan, declarations)
    _insurance_block(assembly, insurance, declarations)
    _investment_block(assembly, investment, declarations)
    if salary is not None:
        salary_fields = _parse_json_payload(salary[1].structured_data)
        verified_income = _finite_or_none(salary_fields.get("gross_salary"))
        if verified_income is None:
            verified_income = _finite_or_none(salary_fields.get("net_salary"))
        if verified_income is not None and verified_income > 0:
            assembly.put(
                "monthly_income", round(verified_income, 2), "DOCUMENT", salary[0].id
            )
    _derived_block(assembly)

    edited_feature_map = {
        "salary_income_proof": {
            "gross_salary": ("monthly_income",),
            "net_salary": ("monthly_income",),
        },
        "credit_report": {
            "outstanding_amount": ("bureau_debt_amount",),
            "sanctioned_amount": ("bureau_credit_amount",),
            "overdue_amount": ("bureau_overdue_amount",),
            "overdue_days": ("bureau_overdue_days",),
            "credit_limit": ("bureau_credit_limit",),
        },
        "loan_document": {
            "loan_amount": ("current_credit_amount", "goods_price"),
            "emi": ("current_loan_annuity",),
        },
        "insurance_document": {"premium": ("insurance_premium",)},
        "investment_statement": {
            "fd": ("fd_amount",),
            "rd": ("rd_contribution",),
            "sip": ("sip_contribution",),
            "mutual_fund": ("mutual_fund_balance",),
            "ppf": ("ppf_contribution",),
            "nps": ("nps_contribution",),
        },
        "bank_import": {
            "imported_transactions": (
                "food_expense",
                "rent_expense",
                "education_expense",
                "healthcare_expense",
                "transport_expense",
                "utility_expense",
                "discretionary_expense",
                "monthly_savings",
                "savings_balance",
                "upi_spending",
                "upi_transaction_count",
                "cash_flow_mean",
                "cash_flow_std",
                "cash_flow_min",
                "cash_flow_negative_months",
            )
        },
    }
    for document_type, (document, extraction) in reviewed.items():
        fields = _parse_json_payload(extraction.structured_data)
        edited = fields.get("__field_provenance__", {})
        for source_field, feature_names in edited_feature_map.get(
            document_type, {}
        ).items():
            if edited.get(source_field) == "USER_EDITED":
                for feature_name in feature_names:
                    if feature_name in assembly.values:
                        assembly.provenance[feature_name] = "USER_EDITED"
                        assembly.sources[feature_name] = document.id
    return assembly


def _parse_json_payload(payload: Any) -> dict[str, Any]:
    import json as _json

    if isinstance(payload, dict):
        return payload
    try:
        parsed = _json.loads(payload or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bank_block(
    assembly: Assembly, bank: tuple | None, bank_import: tuple | None = None
) -> None:
    """Process bank statement and/or bank import file for FRIE features."""
    has_bank = bank is not None
    has_import = bank_import is not None

    if not has_bank and not has_import:
        for name in (
            "food_expense",
            "rent_expense",
            "education_expense",
            "healthcare_expense",
            "transport_expense",
            "utility_expense",
            "discretionary_expense",
            "monthly_savings",
            "savings_balance",
            "upi_spending",
            "upi_transaction_count",
            "cash_flow_mean",
            "cash_flow_std",
            "cash_flow_min",
            "cash_flow_negative_months",
        ):
            assembly.miss(
                name, "bank statement unavailable or unreviewed", "bank_statement"
            )
        return

    # Prefer the reviewed structured import. The PDF is a fallback, not an
    # additional ledger: demo users may upload both representations of the
    # same statement, which must not double their income and spending.
    all_transactions = []
    source_doc_id = None

    if has_bank and not has_import:
        document, extraction = bank
        fields = _parse_json_payload(extraction.structured_data)
        transactions = fields.get("transactions")
        if isinstance(transactions, list) and transactions:
            all_transactions.extend(transactions)
            source_doc_id = document.id

    if has_import:
        import_doc, import_extraction = bank_import
        import_fields = _parse_json_payload(import_extraction.structured_data)
        import_transactions = import_fields.get("imported_transactions")
        if isinstance(import_transactions, list) and import_transactions:
            # Convert imported transactions to standard format
            for txn in import_transactions:
                all_transactions.append(
                    {
                        "date": txn.get("date"),
                        "description": txn.get("description"),
                        "debit": txn.get("debit_amount", 0.0),
                        "credit": txn.get("credit_amount", 0.0),
                        "balance": txn.get("balance"),
                        "category": txn.get("category"),
                    }
                )
            source_doc_id = source_doc_id or import_doc.id

    if not all_transactions and has_bank:
        document, extraction = bank
        fields = _parse_json_payload(extraction.structured_data)
        transactions = fields.get("transactions")
        if isinstance(transactions, list) and transactions:
            all_transactions.extend(transactions)
            source_doc_id = document.id

    if not all_transactions:
        for name in (
            "food_expense",
            "rent_expense",
            "education_expense",
            "healthcare_expense",
            "transport_expense",
            "utility_expense",
            "discretionary_expense",
            "monthly_savings",
            "upi_spending",
            "upi_transaction_count",
            "cash_flow_mean",
            "cash_flow_std",
            "cash_flow_min",
            "cash_flow_negative_months",
        ):
            assembly.miss(name, "no transaction rows available", "bank_statement")
        _balance_from_transactions(assembly, [], source_doc_id)
        return

    # Classify transactions using rule-based categorizer
    # Convert to format expected by classify_transactions
    txns_for_classification = []
    for txn in all_transactions:
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
                "category": txn.get("category"),
            }
        )

    classified = classify_transactions(txns_for_classification)

    # Check for unmatched descriptions
    unmatched = [
        cls.description
        for cls in classified
        if cls.category in ("other_expense", "other_income", "other")
    ]
    bad_dates = sum(1 for cls in classified if cls.date is None)

    if bad_dates:
        for name in (
            "food_expense",
            "rent_expense",
            "education_expense",
            "healthcare_expense",
            "transport_expense",
            "utility_expense",
            "discretionary_expense",
            "monthly_savings",
            "upi_spending",
            "upi_transaction_count",
            "cash_flow_mean",
            "cash_flow_std",
            "cash_flow_min",
            "cash_flow_negative_months",
        ):
            assembly.miss(name, "unparseable transaction rows", "bank_statement")
        _cash_from_monthly(assembly, {}, source_doc_id)
        _balance_from_transactions(assembly, all_transactions, source_doc_id)
        return

    if unmatched:
        for name in (
            "food_expense",
            "rent_expense",
            "education_expense",
            "healthcare_expense",
            "transport_expense",
            "utility_expense",
            "discretionary_expense",
            "monthly_savings",
            "upi_spending",
            "upi_transaction_count",
        ):
            assembly.miss(
                name,
                f"uncategorized transaction descriptions: {sorted(set(unmatched))[:3]}",
                "bank_statement",
            )
        _cash_from_monthly(assembly, {}, source_doc_id)
        _balance_from_transactions(assembly, all_transactions, source_doc_id)
        return

    # Derive monthly features from classified transactions
    # First, build monthly data buckets from classified transactions
    from collections import defaultdict
    from datetime import date as _date
    from datetime import datetime as _datetime

    from app.services.bank_import import BankTransaction

    # Categories from transaction_classifier that we track for expenses
    EXPENSE_CATEGORIES = (
        "food",
        "rent",
        "education",
        "healthcare",
        "transport",
        "utilities",
        "discretionary",
        "emi_debt",
        "investment",
        "insurance",
        "salary_income",
        "other_income",
        "other_expense",
        "other",
    )

    monthly_buckets = defaultdict(
        lambda: {
            "upi_sum": 0.0,
            "upi_count": 0,
            "net": 0.0,
            **{cat: 0.0 for cat in EXPENSE_CATEGORIES},
        }
    )

    for cls in classified:
        # Parse date string to date object
        txn_date = None
        if cls.date:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    txn_date = _datetime.strptime(cls.date, fmt).date()
                    break
                except (ValueError, AttributeError):
                    continue

        # Also populate monthly buckets for _cash_from_monthly and feature derivation
        if txn_date:
            month_key = f"{txn_date.month:02d}/{txn_date.year}"
            debit = cls.amount if cls.transaction_type == "debit" else 0.0
            credit = cls.amount if cls.transaction_type == "credit" else 0.0
            bucket = monthly_buckets[month_key]
            bucket["net"] += credit - debit
            if debit > 0:
                lowered = cls.description.lower()
                if any(kw in lowered for kw in TRANSFER_KEYWORDS):
                    pass  # Skip transfers
                else:
                    # Use the already-classified category from transaction_classifier
                    cat = cls.category
                    if cat in bucket:
                        bucket[cat] += debit
                    # Also track UPI
                    if any(kw in lowered for kw in UPI_KEYWORDS):
                        bucket["upi_sum"] += debit
                        bucket["upi_count"] += 1

    if not monthly_buckets or len(monthly_buckets) < 12:
        for name in (
            "food_expense",
            "rent_expense",
            "education_expense",
            "healthcare_expense",
            "transport_expense",
            "utility_expense",
            "discretionary_expense",
            "monthly_savings",
            "upi_spending",
            "upi_transaction_count",
            "cash_flow_mean",
            "cash_flow_std",
            "cash_flow_min",
            "cash_flow_negative_months",
        ):
            assembly.miss(
                name,
                "insufficient months for monthly aggregation (need 12)",
                "bank_statement",
            )
        _balance_from_transactions(assembly, all_transactions, source_doc_id)
        return

    # Compute monthly averages from buckets
    # Map transaction_classifier categories to FRIE feature names
    category_to_feature = {
        "food": "food_expense",
        "rent": "rent_expense",
        "education": "education_expense",
        "healthcare": "healthcare_expense",
        "transport": "transport_expense",
        "utilities": "utility_expense",
        "discretionary": "discretionary_expense",
    }

    months = sorted(monthly_buckets.keys())
    for cat, feature_name in category_to_feature.items():
        values = [monthly_buckets[month].get(cat, 0.0) for month in months]
        assembly.put(
            feature_name,
            round(sum(values) / len(values), 2),
            "DOCUMENT",
            source_doc_id,
            "READY",
            0.9,
        )

    upi_sums = [monthly_buckets[month]["upi_sum"] for month in months]
    upi_counts = [monthly_buckets[month]["upi_count"] for month in months]
    assembly.put(
        "upi_spending",
        round(sum(upi_sums) / len(upi_sums), 2),
        "DOCUMENT",
        source_doc_id,
        "READY",
        0.9,
    )
    assembly.put(
        "upi_transaction_count",
        int(round(sum(upi_counts) / len(upi_counts))),
        "DOCUMENT",
        source_doc_id,
        "READY",
        0.9,
    )

    nets = [monthly_buckets[month]["net"] for month in months]
    assembly.put(
        "monthly_savings",
        round(max(sum(nets) / len(nets), 0.0), 2),
        "DOCUMENT",
        source_doc_id,
        "READY",
        0.9,
    )

    import statistics as _statistics

    mean = sum(nets) / len(nets)
    assembly.put("cash_flow_mean", round(mean, 2), "DERIVED", source_doc_id)
    assembly.put(
        "cash_flow_std",
        round(_statistics.pstdev(nets), 2) if len(nets) > 1 else 0.0,
        "DERIVED",
        source_doc_id,
    )
    assembly.put("cash_flow_min", round(min(nets), 2), "DERIVED", source_doc_id)
    assembly.put(
        "cash_flow_negative_months",
        sum(1 for net in nets if net < 0),
        "DERIVED",
        source_doc_id,
    )

    _balance_from_transactions(assembly, all_transactions, source_doc_id)
    _cash_from_monthly(assembly, dict(monthly_buckets), source_doc_id)


def _month_key(raw: Any) -> str | None:
    parsed = _parse_calendar_date(raw)
    return f"{parsed.month:02d}/{parsed.year}" if parsed else None


def _finite_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _categorize(description: str) -> str | None:
    lowered = description.lower()
    for category, keywords in EXPENSE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category
    return None


def _cash_from_monthly(
    assembly: Assembly, monthly: dict, document_id: int | None
) -> None:
    """Cash statistics come from statement net flows only; income effects are already netted."""
    names = (
        "cash_flow_mean",
        "cash_flow_std",
        "cash_flow_min",
        "cash_flow_negative_months",
    )
    if not monthly or len(monthly) < CASH_MIN_MONTHS:
        reason = (
            "bank statement unavailable or unreviewed"
            if not monthly
            else f"only {len(monthly)} statement months available (need {CASH_MIN_MONTHS})"
        )
        for name in names:
            assembly.miss(name, reason, "bank_statement")
        return
    import statistics as _statistics

    nets = [monthly[month]["net"] for month in sorted(monthly.keys())]
    mean = sum(nets) / len(nets)
    assembly.put("cash_flow_mean", round(mean, 2), "DERIVED", document_id)
    assembly.put(
        "cash_flow_std",
        round(_statistics.pstdev(nets), 2) if len(nets) > 1 else 0.0,
        "DERIVED",
        document_id,
    )
    assembly.put("cash_flow_min", round(min(nets), 2), "DERIVED", document_id)
    assembly.put(
        "cash_flow_negative_months",
        sum(1 for net in nets if net < 0),
        "DERIVED",
        document_id,
    )


def _balance_from_transactions(
    assembly: Assembly, transactions: list, document_id: int | None
) -> None:
    balances = [
        txn["balance"]
        for txn in transactions
        if isinstance(txn, dict) and _finite_or_none(txn.get("balance")) is not None
    ]
    if not balances:
        assembly.miss(
            "savings_balance",
            "no balance records in reviewed statement",
            "bank_statement",
        )
        return
    assembly.put(
        "savings_balance", round(float(balances[-1]), 2), "DOCUMENT", document_id
    )


def _credit_block(assembly: Assembly, credit, declarations: dict[str, Any]) -> None:
    names_counts = (
        "bureau_account_count",
        "active_credit_count",
        "closed_credit_count",
        "previous_application_count",
        "previous_approved_count",
        "previous_refused_count",
        "total_installments",
        "total_on_time_payments",
        "total_late_payments",
    )
    names_amounts = (
        "bureau_credit_amount",
        "bureau_debt_amount",
        "bureau_credit_limit",
        "bureau_overdue_amount",
        "bureau_overdue_days",
        "bureau_overdue_account_count",
        "credit_prolongation_count",
        "total_amount_due",
        "total_amount_paid",
        "total_payment_delay_days",
        "average_payment_delay",
        "payment_difference",
        "previous_credit_amount",
        "previous_avg_credit",
        "previous_avg_annuity",
        "previous_avg_down_payment",
        "avg_credit_card_balance",
        "max_credit_card_balance",
        "avg_credit_limit",
        "total_card_drawings",
        "total_card_payments",
        "avg_minimum_payment",
        "avg_credit_utilisation",
        "max_card_dpd",
        "max_card_dpd_default",
        "pos_account_records",
        "avg_pos_installments",
        "avg_future_installments",
        "pos_dpd_count",
        "max_pos_dpd",
        "max_pos_dpd_default",
    )
    if credit is None:
        if declarations.get("has_loan") == "no":
            # No current obligations: current-state debt facts are zero.
            # Anything involving history (including closed tradelines and past
            # applications) stays unknown -- a "no" to a current loan says
            # nothing about the past.
            assembly.put("bureau_debt_amount", 0.0, "USER")
            assembly.put("bureau_overdue_amount", 0.0, "USER")
            assembly.put("bureau_overdue_days", 0, "USER")
            assembly.put("bureau_overdue_account_count", 0, "USER")
            for name in (
                "bureau_account_count",
                "active_credit_count",
                "closed_credit_count",
                "bureau_credit_amount",
                "bureau_credit_limit",
                "credit_prolongation_count",
                "total_installments",
                "total_amount_due",
                "total_amount_paid",
                "total_late_payments",
                "total_on_time_payments",
                "total_payment_delay_days",
                "average_payment_delay",
                "payment_difference",
                "previous_application_count",
                "previous_approved_count",
                "previous_refused_count",
                "previous_credit_amount",
                "previous_avg_credit",
                "previous_avg_annuity",
                "previous_avg_down_payment",
                "avg_credit_card_balance",
                "max_credit_card_balance",
                "avg_credit_limit",
                "total_card_drawings",
                "total_card_payments",
                "avg_minimum_payment",
                "avg_credit_utilisation",
                "max_card_dpd",
                "max_card_dpd_default",
                "pos_account_records",
                "avg_pos_installments",
                "avg_future_installments",
                "pos_dpd_count",
                "max_pos_dpd",
                "max_pos_dpd_default",
            ):
                assembly.miss(
                    name,
                    "credit history unknown (confirmed no current loan; past history not established)",
                    "credit_report",
                )
            for name in (
                "previous_approval_ratio",
                "bureau_overdue_ratio",
                "on_time_payment_ratio",
                "payment_coverage_ratio",
            ):
                assembly.miss(
                    name,
                    "no credit history on record (confirmed no loan)",
                    "credit_report",
                )
            return
        reason = "credit report unavailable or unreviewed"
        if declarations.get("has_loan") in (None, "unknown"):
            reason = "credit history unknown (no confirmed statement)"
        for name in (
            names_counts
            + names_amounts
            + (
                "previous_approval_ratio",
                "bureau_overdue_ratio",
                "on_time_payment_ratio",
                "payment_coverage_ratio",
            )
        ):
            assembly.miss(name, reason, "credit_report")
        return

    document, extraction = credit
    records = credit_records.parse_credit_records(_raw_text_of(extraction))
    tradelines = records["tradelines"]
    installments = records["installments"]
    prevapps = records["previous_applications"]
    cards = records["card_months"]
    pos = records["pos_records"]
    if not tradelines and not installments and not prevapps and not cards and not pos:
        for name in names_counts + names_amounts:
            assembly.miss(
                name, "no parseable credit records in reviewed report", "credit_report"
            )
        for name in (
            "previous_approval_ratio",
            "bureau_overdue_ratio",
            "on_time_payment_ratio",
            "payment_coverage_ratio",
        ):
            assembly.miss(
                name, "no parseable credit records in reviewed report", "credit_report"
            )
        return

    def _sum(rows, key):
        return round(sum(float(row.get(key) or 0.0) for row in rows), 2)

    def _mean(rows, key):
        if not rows:
            return None
        return round(sum(float(row.get(key) or 0.0) for row in rows) / len(rows), 2)

    def _mean_or_miss(rows, key, name, reason):
        value = _mean(rows, key)
        if value is None:
            assembly.miss(name, reason, "credit_report")
        else:
            assembly.put(name, value, "DOCUMENT", document.id)

    def _max_or_miss(rows, key, name, reason, round_digits=2):
        values = [row.get(key) or 0 for row in rows]
        if not rows:
            assembly.miss(name, reason, "credit_report")
            return
        peak = max(values)
        if round_digits == 0:
            assembly.put(name, int(peak), "DOCUMENT", document.id)
        else:
            assembly.put(
                name, round(float(peak), round_digits), "DOCUMENT", document.id
            )

    assembly.put("bureau_account_count", len(tradelines), "DOCUMENT", document.id)
    assembly.put(
        "active_credit_count",
        sum(1 for row in tradelines if str(row.get("status", "")).lower() == "active"),
        "DOCUMENT",
        document.id,
    )
    assembly.put(
        "closed_credit_count",
        sum(1 for row in tradelines if str(row.get("status", "")).lower() == "closed"),
        "DOCUMENT",
        document.id,
    )
    assembly.put(
        "bureau_credit_amount", _sum(tradelines, "limit"), "DOCUMENT", document.id
    )
    assembly.put(
        "bureau_debt_amount", _sum(tradelines, "debt"), "DOCUMENT", document.id
    )
    assembly.put(
        "bureau_credit_limit", _sum(tradelines, "limit"), "DOCUMENT", document.id
    )
    assembly.put(
        "bureau_overdue_amount", _sum(tradelines, "overdue"), "DOCUMENT", document.id
    )
    assembly.put(
        "bureau_overdue_days",
        int(sum(int(row.get("dpd") or 0) for row in tradelines)),
        "DOCUMENT",
        document.id,
    )
    assembly.put(
        "bureau_overdue_account_count",
        sum(1 for row in tradelines if int(row.get("dpd") or 0) > 0),
        "DOCUMENT",
        document.id,
    )
    assembly.put(
        "credit_prolongation_count",
        int(sum(int(row.get("prolong") or 0) for row in tradelines)),
        "DOCUMENT",
        document.id,
    )

    assembly.put("total_installments", len(installments), "DOCUMENT", document.id)
    assembly.put("total_amount_due", _sum(installments, "due"), "DOCUMENT", document.id)
    assembly.put(
        "total_amount_paid", _sum(installments, "paid"), "DOCUMENT", document.id
    )
    delays: list[int] = []
    timing_known = bool(installments)
    for row in installments:
        delay = _installment_delay_days(row.get("date"), row.get("paid_date"))
        if delay is None:
            timing_known = False
            break
        if delay > 0:
            delays.append(delay)
    if not installments:
        for name in (
            "total_late_payments",
            "total_on_time_payments",
            "total_payment_delay_days",
            "average_payment_delay",
        ):
            assembly.miss(
                name, "no installment records in reviewed report", "credit_report"
            )
    elif not timing_known:
        for name in (
            "total_late_payments",
            "total_on_time_payments",
            "total_payment_delay_days",
            "average_payment_delay",
        ):
            assembly.miss(
                name,
                "payment timing unavailable for some installments",
                "credit_report",
            )
    else:
        assembly.put("total_late_payments", len(delays), "DOCUMENT", document.id)
        assembly.put(
            "total_on_time_payments",
            len(installments) - len(delays),
            "DOCUMENT",
            document.id,
        )
        assembly.put(
            "total_payment_delay_days", int(sum(delays)), "DOCUMENT", document.id
        )
        assembly.put(
            "average_payment_delay",
            round(sum(delays) / len(delays), 2) if delays else 0.0,
            "DOCUMENT",
            document.id,
        )
    assembly.put(
        "payment_difference",
        round(
            sum(
                float(row.get("paid") or 0.0) - float(row.get("due") or 0.0)
                for row in installments
            ),
            2,
        ),
        "DOCUMENT",
        document.id,
    )

    assembly.put("previous_application_count", len(prevapps), "DOCUMENT", document.id)
    assembly.put(
        "previous_approved_count",
        sum(1 for row in prevapps if str(row.get("status", "")).lower() == "approved"),
        "DOCUMENT",
        document.id,
    )
    assembly.put(
        "previous_refused_count",
        sum(
            1
            for row in prevapps
            if str(row.get("status", "")).lower() in ("refused", "rejected")
        ),
        "DOCUMENT",
        document.id,
    )
    assembly.put(
        "previous_credit_amount", _sum(prevapps, "credit"), "DOCUMENT", document.id
    )
    _mean_or_miss(
        prevapps, "credit", "previous_avg_credit", "no previous applications on record"
    )
    _mean_or_miss(
        prevapps,
        "annuity",
        "previous_avg_annuity",
        "no previous applications on record",
    )
    _mean_or_miss(
        prevapps,
        "down",
        "previous_avg_down_payment",
        "no previous applications on record",
    )

    _mean_or_miss(
        cards, "balance", "avg_credit_card_balance", "no card history on record"
    )
    _max_or_miss(
        cards, "balance", "max_credit_card_balance", "no card history on record"
    )
    _mean_or_miss(cards, "limit", "avg_credit_limit", "no card history on record")
    assembly.put(
        "total_card_drawings", _sum(cards, "drawings"), "DOCUMENT", document.id
    )
    assembly.put(
        "total_card_payments", _sum(cards, "payments"), "DOCUMENT", document.id
    )
    _mean_or_miss(cards, "minimum", "avg_minimum_payment", "no card history on record")
    utilizations = [
        float(row.get("balance") or 0.0) / float(row.get("limit") or 0.0)
        for row in cards
        if float(row.get("limit") or 0.0) > 0
    ]
    if utilizations:
        assembly.put(
            "avg_credit_utilisation",
            round(sum(utilizations) / len(utilizations), 4),
            "DOCUMENT",
            document.id,
        )
    else:
        assembly.miss(
            "avg_credit_utilisation", "no card history on record", "credit_report"
        )
    _max_or_miss(
        cards, "dpd", "max_card_dpd", "no card history on record", round_digits=0
    )
    _max_or_miss(
        cards,
        "dpd_default",
        "max_card_dpd_default",
        "no card history on record",
        round_digits=0,
    )

    assembly.put("pos_account_records", len(pos), "DOCUMENT", document.id)
    _mean_or_miss(
        pos, "installments", "avg_pos_installments", "no POS history on record"
    )
    _mean_or_miss(pos, "future", "avg_future_installments", "no POS history on record")
    assembly.put(
        "pos_dpd_count",
        sum(1 for row in pos if int(row.get("dpd") or 0) > 0),
        "DOCUMENT",
        document.id,
    )
    _max_or_miss(pos, "dpd", "max_pos_dpd", "no POS history on record", round_digits=0)
    _max_or_miss(
        pos,
        "dpd_default",
        "max_pos_dpd_default",
        "no POS history on record",
        round_digits=0,
    )

    _ratio_features(assembly)


def _parse_calendar_date(raw: Any) -> Any:
    from datetime import datetime as _datetime

    if not isinstance(raw, str):
        return None
    for dayfirst in (True, False):
        try:
            return _datetime.strptime(
                raw.strip(), "%d/%m/%Y" if dayfirst else "%m/%d/%Y"
            ).date()
        except ValueError:
            continue
    try:
        return _datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _calendar_month(raw: Any) -> str | None:
    parsed = _parse_calendar_date(raw)
    return f"{parsed.year:04d}-{parsed.month:02d}" if parsed else None


def _installment_delay_days(due_raw: Any, paid_raw: Any) -> int | None:
    """Days paid after due (positive means late), mirroring the research definition."""

    due = _parse_calendar_date(due_raw)
    paid = _parse_calendar_date(paid_raw)
    if due is None or paid is None:
        return None
    return (paid - due).days


def _ratio_features(assembly: Assembly) -> None:
    get = assembly.values.get

    def _ratio(name: str, numerator: Any, denominator: Any) -> None:
        try:
            num, den = float(numerator), float(denominator)
        except (TypeError, ValueError):
            assembly.miss(name, "ratio inputs unavailable", "derived")
            return
        if not isfinite(num) or not isfinite(den) or den <= 0:
            assembly.miss(name, "ratio denominator not positive", "derived")
            return
        assembly.put(name, round(num / den, 4), "DERIVED")

    _ratio(
        "previous_approval_ratio",
        get("previous_approved_count"),
        get("previous_application_count"),
    )
    _ratio(
        "bureau_overdue_ratio",
        get("bureau_overdue_amount"),
        get("bureau_credit_amount"),
    )
    _ratio(
        "on_time_payment_ratio",
        get("total_on_time_payments"),
        get("total_installments"),
    )
    _ratio("payment_coverage_ratio", get("total_amount_paid"), get("total_amount_due"))

    income = get("monthly_income")
    annuity = get("current_loan_annuity")
    try:
        income_f, annuity_f = float(income), float(annuity)
        valid = isfinite(income_f) and isfinite(annuity_f) and income_f > 0
    except (TypeError, ValueError):
        valid = False
    if valid:
        assembly.put("current_dti", round(annuity_f / income_f, 4), "DERIVED")
    else:
        assembly.miss("current_dti", "annuity or income unavailable", "derived")
    debt = get("bureau_debt_amount")
    try:
        debt_f = float(debt)
        debt_valid = isfinite(debt_f) and valid
    except (TypeError, ValueError):
        debt_valid = False
    if debt_valid:
        assembly.put("bureau_dti", round(debt_f / income_f, 4), "DERIVED")
    else:
        assembly.miss("bureau_dti", "bureau debt or income unavailable", "derived")

    expense_parts = [
        get(name)
        for name in (
            "food_expense",
            "rent_expense",
            "education_expense",
            "healthcare_expense",
            "transport_expense",
            "utility_expense",
            "discretionary_expense",
        )
    ]
    annuity_value = get("current_loan_annuity")
    savings = get("monthly_savings")
    upi = get("upi_spending")
    try:
        parts = [float(part) for part in expense_parts]
        expense_f = sum(parts)
        emi_raw, savings_f, upi_f = float(annuity_value), float(savings), float(upi)
        emi_f = min(emi_raw, 0.50 * income_f)
        money_valid = (
            all(isfinite(v) for v in (expense_f, emi_f, savings_f, upi_f)) and valid
        )
    except (TypeError, ValueError):
        money_valid = False
    if money_valid:
        assembly.put("synthetic_total_expense", round(expense_f, 2), "DERIVED")
        assembly.put(
            "synthetic_spending_ratio", round(expense_f / income_f, 4), "DERIVED"
        )
        assembly.put(
            "synthetic_total_emi", round(min(emi_f, 0.50 * income_f), 2), "DERIVED"
        )
        assembly.put(
            "available_surplus",
            round(max(income_f - expense_f - min(emi_f, 0.50 * income_f), 0.0), 2),
            "DERIVED",
        )
        assembly.put(
            "savings_rate",
            round(min(max(savings_f / income_f, 0.0), 0.80), 4),
            "DERIVED",
        )
        assembly.put(
            "digital_payment_ratio",
            round((upi_f / expense_f) if expense_f > 0 else 0.0, 4),
            "DERIVED",
        )
    else:
        for name in (
            "synthetic_total_expense",
            "synthetic_spending_ratio",
            "synthetic_total_emi",
            "available_surplus",
            "savings_rate",
            "digital_payment_ratio",
        ):
            assembly.miss(name, "expense/emi/savings/income unavailable", "derived")


def _raw_text_of(extraction) -> str:
    return extraction.raw_text or ""


def _loan_block(assembly: Assembly, loan, declarations: dict[str, Any]) -> None:
    if loan is not None:
        document, extraction = loan
        fields = _parse_json_payload(extraction.structured_data)
        amount = _finite_or_none(fields.get("loan_amount"))
        emi = _finite_or_none(fields.get("emi"))
        if amount is None or emi is None:
            for name in (
                "current_credit_amount",
                "current_loan_annuity",
                "goods_price",
            ):
                assembly.miss(
                    name, "loan figures missing in reviewed document", "loan_document"
                )
            return
        assembly.put("current_credit_amount", round(amount, 2), "DOCUMENT", document.id)
        assembly.put("current_loan_annuity", round(emi, 2), "DOCUMENT", document.id)
        assembly.put("goods_price", round(amount, 2), "DOCUMENT", document.id)
        return
    if declarations.get("has_loan") == "no":
        assembly.put("current_credit_amount", 0.0, "USER")
        assembly.put("current_loan_annuity", 0.0, "USER")
        assembly.put("goods_price", 0.0, "USER")
        return
    for name in ("current_credit_amount", "current_loan_annuity", "goods_price"):
        assembly.miss(name, "loan document unavailable or unreviewed", "loan_document")


def _insurance_block(
    assembly: Assembly, insurance, declarations: dict[str, Any]
) -> None:
    status = declarations.get("insurance_status")
    flags = {"health": 0, "life": 0}
    if status in ("health", "both"):
        flags["health"] = 1
    if status in ("life", "both"):
        flags["life"] = 1
    if status in ("health", "life", "both", "none"):
        assembly.put("health_insurance", flags["health"], "USER")
        assembly.put("life_insurance", flags["life"], "USER")
    else:
        assembly.miss(
            "health_insurance", "insurance holding unknown", "insurance_document"
        )
        assembly.miss(
            "life_insurance", "insurance holding unknown", "insurance_document"
        )

    if insurance is not None:
        document, extraction = insurance
        fields = _parse_json_payload(extraction.structured_data)
        premium = _finite_or_none(fields.get("premium"))
        if premium is None:
            assembly.miss(
                "insurance_premium",
                "premium missing in reviewed document",
                "insurance_document",
            )
        else:
            assembly.put(
                "insurance_premium", round(premium, 2), "DOCUMENT", document.id
            )
        dates = fields.get("payment_dates")
        months = set()
        if isinstance(dates, list):
            for raw in dates:
                month = _calendar_month(raw)
                if month:
                    months.add(month)
        if len(months) >= 12:
            assembly.put(
                "insurance_payment_consistency",
                round(len(months) / 12.0, 4),
                "DOCUMENT",
                document.id,
            )
        else:
            assembly.miss(
                "insurance_payment_consistency",
                "fewer than 12 premium periods on record"
                if dates
                else "premium payment history unavailable",
                "insurance_document",
            )
        return
    if status == "none":
        assembly.put("insurance_premium", 0.0, "USER")
        assembly.miss(
            "insurance_payment_consistency",
            "no policy, so no payment history exists",
            "insurance_document",
        )
        return
    assembly.miss(
        "insurance_premium",
        "insurance document unavailable or unreviewed",
        "insurance_document",
    )
    assembly.miss(
        "insurance_payment_consistency",
        "premium payment history unavailable",
        "insurance_document",
    )


_INVESTMENT_FIELDS = (
    ("inv_fd", "fd_amount"),
    ("inv_rd", "rd_contribution"),
    ("inv_sip", "sip_contribution"),
    ("inv_mutual_fund", "mutual_fund_balance"),
    ("inv_ppf", "ppf_contribution"),
    ("inv_nps", "nps_contribution"),
)
_INVESTMENT_KEYS = {
    "fd_amount": "fd",
    "rd_contribution": "rd",
    "sip_contribution": "sip",
    "mutual_fund_balance": "mutual_fund",
    "ppf_contribution": "ppf",
    "nps_contribution": "nps",
}


def _investment_block(
    assembly: Assembly, investment, declarations: dict[str, Any]
) -> None:
    fields: dict[str, Any] = {}
    document_id: int | None = None
    if investment is not None:
        document, extraction = investment
        fields = _parse_json_payload(extraction.structured_data)
        document_id = document.id
    for declaration_key, feature in _INVESTMENT_FIELDS:
        extracted = _finite_or_none(fields.get(_INVESTMENT_KEYS[feature]))
        if extracted is not None:
            assembly.put(feature, round(extracted, 2), "DOCUMENT", document_id)
        elif declarations.get(declaration_key) == "no":
            assembly.put(feature, 0.0, "USER")
        else:
            assembly.miss(
                feature,
                "holding unconfirmed and no reviewed statement",
                "investment_statement",
            )


def _derived_block(assembly: Assembly) -> None:
    _ratio_features(assembly)


def _valid_for_contract(name: str, value: Any, numeric_names: set[str]) -> bool:
    if isinstance(value, bool):
        return False
    if name in numeric_names:
        return isinstance(value, (int, float)) and isfinite(float(value))
    return isinstance(value, str) and value in MODEL_CATEGORICAL_LEVELS.get(name, ())


def persist_assembly(
    db: Session, user, assembly: Assembly, numeric_names: set[str]
) -> int:
    """Replace the user's stored features with the assembled valid values.

    Idempotent: previous rows are deleted first, so repeated builds never
    duplicate. Only contract-valid values are stored; anything else stays
    missing with its reason.
    """

    from app.db.models import FinancialFeature

    db.query(FinancialFeature).filter(FinancialFeature.user_id == user.id).delete()
    stored = 0
    for name, value in assembly.values.items():
        if not _valid_for_contract(name, value, numeric_names):
            continue
        if isinstance(value, (int, float)):
            row = FinancialFeature(
                user_id=user.id,
                feature_name=name,
                feature_type="NUMERIC",
                value_num=float(value),
                value_text=None,
                provenance=assembly.provenance.get(name, "DERIVED"),
                status=assembly.status.get(name, "READY"),
                confidence=assembly.confidence.get(name, 1.0),
                source_document_id=assembly.sources.get(name),
            )
        else:
            row = FinancialFeature(
                user_id=user.id,
                feature_name=name,
                feature_type="CATEGORICAL",
                value_num=None,
                value_text=value,
                provenance=assembly.provenance.get(name, "DERIVED"),
                status=assembly.status.get(name, "READY"),
                confidence=assembly.confidence.get(name, 1.0),
                source_document_id=assembly.sources.get(name),
            )
        db.add(row)
        stored += 1
    db.flush()
    return stored


# Feature group definitions for completeness reporting
FEATURE_GROUPS = {
    "Income & Employment": (
        "monthly_income",
        "income_type",
        "employment_years",
        "occupation",
        "organization_type",
        "contract_type",
        "age_years",
        "city_tier",
        "occupation_band",
        "indian_household_size",
        "gender",
        "family_status",
        "education_level",
        "housing_type",
        "owns_car",
        "owns_property",
        "family_size",
        "children_count",
    ),
    "Bank & Cash Flow": (
        "food_expense",
        "rent_expense",
        "education_expense",
        "healthcare_expense",
        "transport_expense",
        "utility_expense",
        "discretionary_expense",
        "monthly_savings",
        "savings_balance",
        "upi_spending",
        "upi_transaction_count",
        "cash_flow_mean",
        "cash_flow_std",
        "cash_flow_min",
        "cash_flow_negative_months",
        "synthetic_total_expense",
        "synthetic_total_emi",
        "available_surplus",
        "savings_rate",
        "synthetic_spending_ratio",
        "digital_payment_ratio",
    ),
    "Credit & Repayment": (
        "bureau_account_count",
        "active_credit_count",
        "closed_credit_count",
        "bureau_credit_amount",
        "bureau_debt_amount",
        "bureau_credit_limit",
        "bureau_overdue_amount",
        "bureau_overdue_days",
        "bureau_overdue_account_count",
        "credit_prolongation_count",
        "total_installments",
        "total_amount_due",
        "total_amount_paid",
        "total_late_payments",
        "total_on_time_payments",
        "average_payment_delay",
        "total_payment_delay_days",
        "payment_difference",
        "on_time_payment_ratio",
        "payment_coverage_ratio",
        "previous_application_count",
        "previous_approved_count",
        "previous_refused_count",
        "previous_credit_amount",
        "previous_avg_credit",
        "previous_avg_annuity",
        "previous_avg_down_payment",
        "avg_credit_card_balance",
        "max_credit_card_balance",
        "avg_credit_limit",
        "total_card_drawings",
        "total_card_payments",
        "avg_minimum_payment",
        "avg_credit_utilisation",
        "max_card_dpd",
        "max_card_dpd_default",
        "pos_account_records",
        "avg_pos_installments",
        "avg_future_installments",
        "pos_dpd_count",
        "max_pos_dpd",
        "max_pos_dpd_default",
        "current_dti",
        "bureau_dti",
        "previous_approval_ratio",
        "bureau_overdue_ratio",
        "current_credit_amount",
        "current_loan_annuity",
        "goods_price",
    ),
    "Insurance": (
        "health_insurance",
        "life_insurance",
        "insurance_premium",
        "insurance_payment_consistency",
    ),
    "Investments": (
        "fd_amount",
        "rd_contribution",
        "sip_contribution",
        "mutual_fund_balance",
        "ppf_contribution",
        "nps_contribution",
    ),
    "Derived": (
        "synthetic_total_expense",
        "synthetic_total_emi",
        "available_surplus",
        "savings_rate",
        "synthetic_spending_ratio",
        "digital_payment_ratio",
        "cash_flow_mean",
        "cash_flow_std",
        "cash_flow_min",
        "cash_flow_negative_months",
        "monthly_savings",
        "current_dti",
        "bureau_dti",
        "previous_approval_ratio",
        "bureau_overdue_ratio",
        "on_time_payment_ratio",
        "payment_coverage_ratio",
        "indian_household_size",
        "occupation_band",
        "city_tier",
    ),
}


def _calculate_group_completeness(
    assembly: Assembly, contract
) -> dict[str, dict[str, int]]:
    """Calculate completeness by feature group."""
    numeric_names = set(contract.numeric_features)
    group_results = {}

    for group_name, features in FEATURE_GROUPS.items():
        group_features = [f for f in features if f in contract.feature_names]
        available = sum(
            1
            for name in group_features
            if name in assembly.values
            and _valid_for_contract(name, assembly.values[name], numeric_names)
        )
        total = len(group_features)
        group_results[group_name] = {
            "available": available,
            "total": total,
            "percentage": round(available / total * 100, 1) if total > 0 else 0.0,
        }

    return group_results


def readiness_report(assembly: Assembly, contract) -> dict[str, Any]:
    """Deterministic readiness from a fresh assembly (no persistence involved)."""

    numeric_names = set(contract.numeric_features)
    available = sum(
        1
        for name, value in assembly.values.items()
        if _valid_for_contract(name, value, numeric_names)
    )
    by_provenance: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for name, value in assembly.values.items():
        if _valid_for_contract(name, value, numeric_names):
            group = assembly.provenance.get(name, "DERIVED")
            by_provenance[group] = by_provenance.get(group, 0) + 1
            status = assembly.status.get(name, "READY")
            by_status[status] = by_status.get(status, 0) + 1

    group_completeness = _calculate_group_completeness(assembly, contract)

    if available >= contract.feature_count:
        status = "READY"
    elif available > 0:
        status = "PARTIALLY_READY"
    else:
        status = "NOT_READY"
    return {
        "total_required": contract.feature_count,
        "available": available,
        "missing": [dict(entry) for entry in assembly.missing],
        "status": status,
        "by_provenance": by_provenance,
        "by_status": by_status,
        "group_completeness": group_completeness,
    }


def build_features(db: Session, user) -> dict[str, Any]:
    """Assemble, validate, and persist the user's features idempotently."""

    from app.core.feature_contract import get_feature_contract

    contract = get_feature_contract()
    assembly = assemble(db, user)
    stored = persist_assembly(db, user, assembly, set(contract.numeric_features))
    report = readiness_report(assembly, contract)
    report["stored"] = stored
    return report


def get_user_completeness(db: Session, user) -> dict[str, Any]:
    """Get real-world completeness report for a user without rebuilding."""
    from app.core.feature_contract import get_feature_contract
    from app.db.models import FinancialFeature

    contract = get_feature_contract()
    features = (
        db.query(FinancialFeature).filter(FinancialFeature.user_id == user.id).all()
    )

    # Build a mock assembly for completeness calculation
    class MockAssembly:
        def __init__(self, features):
            self.values = {
                f.feature_name: f.value_num if f.value_num is not None else f.value_text
                for f in features
            }
            self.provenance = {f.feature_name: f.provenance for f in features}
            self.status = {f.feature_name: f.status for f in features}
            self.confidence = {f.feature_name: f.confidence for f in features}
            self.missing = []

    assembly = MockAssembly(features)
    report = readiness_report(assembly, contract)
    return report
