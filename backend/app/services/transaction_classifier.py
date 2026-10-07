"""Rule-based transaction classification for FRIE feature derivation.

Classifies transactions into standard categories using transparent
merchant/narration keyword matching. Extensible for custom rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Category definitions with keywords for matching
# Order matters: more specific categories first
TRANSACTION_CATEGORIES = [
    # Income
    ("salary_income", (
        "salary", "payroll", "wages", "stipend", "pension", "annuity",
        "salary credit", "payroll credit"
    )),
    
    # Recurring essential expenses
    ("rent", (
        "rent", "landlord", "house rent", "flat rent", "lease", "housing rent"
    )),
    ("food", (
        "swiggy", "zomato", "restaurant", "food", "grocery", "supermarket",
        "bigbasket", "dominos", "cafe", "dining", "meal", "canteen",
        "blinkit", "zepto", "dunzo", "nature's basket", "more supermarket",
        "reliance fresh", "dmart", "avenue supermarket"
    )),
    ("education", (
        "school", "college", "tuition", "education", "fees", "university",
        "course", "exam", "coaching", "byju", "unacademy", "vedantu",
        "school fees", "college fees", "tuition fees"
    )),
    ("healthcare", (
        "hospital", "clinic", "pharmacy", "medical", "health", "diagnostic",
        "doctor", "apollo", "fortis", "max hospital", "medplus", "1mg",
        "pharmeasy", "netmeds", "lab", "pathology", "radiology", "dental",
        "eye care", "physio", "therapy"
    )),
    ("transport", (
        "uber", "ola", "fuel", "petrol", "diesel", "cng", "metro", "transport",
        "taxi", "cab", "railway", "irctc", "bus", "auto", "rapido",
        "fuel station", "hp petrol", "bharat petroleum", "indian oil",
        "shell", "reliance petrol", "ev charging"
    )),
    ("utilities", (
        "electricity", "water bill", "gas bill", "mobile recharge", "recharge",
        "broadband", "utility", "dth", "airtel", "jio", "vi ", "vodafone",
        "bsnl", "tata power", "bSES", "mahadiscom", "kseb", "tneb",
        "water supply", "municipal", "property tax", "maintenance"
    )),
    
    # Discretionary
    ("discretionary", (
        "shopping", "mall", "amazon", "flipkart", "myntra", "ajio", "meesho",
        "entertainment", "movie", "bookmyshow", "pvr", "inox", "salon",
        "gym", "fitness", "travel", "flight", "hotel", "makemytrip",
        "goibibo", "yatra", "ixigo", "cleartrip", "oyo", "airbnb",
        "spotify", "netflix", "prime", "hotstar", "sony liv", "zee5",
        "gaming", "steam", "playstation", "xbox"
    )),
    
    # Financial obligations
    ("emi_debt", (
        "emi", "loan", "installment", "instalment", "annuity", "repayment",
        "hdfc loan", "icici loan", "sbi loan", "axis loan", "kotak loan",
        "bajaj finance", "home credit", "tata capital", "l&t finance",
        "credit card", "cc bill", "card payment", "visa", "mastercard",
        "rupay", "outstanding", "due amount", "minimum due"
    )),
    
    # Investments
    ("investment", (
        "sip", "mutual", "fixed deposit", "fd ", "recurring deposit", "rd ",
        "ppf", "nps", "investment", "elss", "equity", "stocks", "shares",
        "zerodha", "groww", "upstox", "angel one", "5paisa", "kite",
        "coin", "smallcase", "etf", "gold bond", "sovereign gold"
    )),
    
    # Digital payments
    ("upi", (
        "upi", "phonepe", "google pay", "gpay", "paytm", "bhim", "amazon pay",
        "whatsapp pay", "qr pay", "scan pay", "collect request"
    )),
    
    # Transfers
    ("transfer", (
        "transfer", "neft", "rtgs", "imps", "ach", "eft", "wire",
        "self transfer", "own account", "family", "mother", "father",
        "spouse", "wife", "husband", "brother", "sister"
    )),
    
    # Insurance
    ("insurance", (
        "insurance", "premium", "lic", "hdfc life", "icici prudential",
        "sbi life", "max life", "tata aia", "bajaj allianz", "star health",
        "religare", "care health", "policybazaar", "term plan", "health plan"
    )),
]


@dataclass
class ClassifiedTransaction:
    """Transaction with classification result."""
    date: Any
    description: str
    transaction_type: str  # "credit" or "debit"
    amount: float
    balance: float | None
    category: str
    confidence: float  # 0.0 to 1.0
    matched_keyword: str | None


def classify_transaction(
    description: str,
    transaction_type: str,
    amount: float,
    balance: float | None = None,
    category_override: str | None = None,
) -> ClassifiedTransaction:
    """Classify a single transaction using keyword matching.
    
    Returns classified transaction with category and confidence.
    """
    valid_categories = {category for category, _ in TRANSACTION_CATEGORIES} | {"other", "other_income", "other_expense"}
    if category_override in valid_categories:
        return ClassifiedTransaction(None, description, transaction_type, amount, balance, category_override, 1.0, "user_edit")
    desc_lower = description.lower().strip()
    
    # First pass: exact/category-specific matching
    best_category = "other"
    best_confidence = 0.0
    matched_keyword = None
    
    for category, keywords in TRANSACTION_CATEGORIES:
        for keyword in keywords:
            if keyword in desc_lower:
                # Confidence based on keyword specificity and position
                # Longer keywords that appear earlier = higher confidence
                keyword_len = len(keyword)
                position_bonus = 1.0 - (desc_lower.find(keyword) / max(len(desc_lower), 1)) * 0.3
                length_bonus = min(keyword_len / 20.0, 0.3)
                confidence = min(0.5 + position_bonus + length_bonus, 0.95)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_category = category
                    matched_keyword = keyword
    
    # Second pass: type-based inference for uncategorized
    if best_category == "other":
        if transaction_type == "credit":
            # Credits without salary keywords likely "other_income"
            if any(kw in desc_lower for kw in ("refund", "cashback", "reward", "interest", "dividend")):
                best_category = "other_income"
                best_confidence = 0.6
                matched_keyword = "refund/cashback"
            else:
                best_category = "other_income"
                best_confidence = 0.3
        else:
            # Debits without clear category
            best_category = "other_expense"
            best_confidence = 0.2
    
    return ClassifiedTransaction(
        date=None,  # Will be set by caller
        description=description,
        transaction_type=transaction_type,
        amount=amount,
        balance=balance,
        category=best_category,
        confidence=best_confidence,
        matched_keyword=matched_keyword,
    )


def classify_transactions(transactions: list[dict[str, Any]]) -> list[ClassifiedTransaction]:
    """Classify a list of transactions."""
    classified = []
    for txn in transactions:
        cls = classify_transaction(
            description=txn.get("description", ""),
            transaction_type=txn.get("transaction_type", "debit"),
            amount=txn.get("debit_amount", 0) or txn.get("credit_amount", 0),
            balance=txn.get("balance"),
            category_override=txn.get("category"),
        )
        cls.date = txn.get("transaction_date")
        classified.append(cls)
    return classified


def get_category_stats(classified: list[ClassifiedTransaction]) -> dict[str, dict[str, float]]:
    """Get aggregated statistics by category."""
    stats = {}
    for cls in classified:
        if cls.category not in stats:
            stats[cls.category] = {
                "total_amount": 0.0,
                "count": 0,
                "avg_confidence": 0.0,
                "credit_amount": 0.0,
                "debit_amount": 0.0,
            }
        cat_stats = stats[cls.category]
        cat_stats["total_amount"] += cls.amount
        cat_stats["count"] += 1
        cat_stats["avg_confidence"] = (
            (cat_stats["avg_confidence"] * (cat_stats["count"] - 1) + cls.confidence)
            / cat_stats["count"]
        )
        if cls.transaction_type == "credit":
            cat_stats["credit_amount"] += cls.amount
        else:
            cat_stats["debit_amount"] += cls.amount
    
    # Round
    for cat_stats in stats.values():
        cat_stats["total_amount"] = round(cat_stats["total_amount"], 2)
        cat_stats["avg_confidence"] = round(cat_stats["avg_confidence"], 3)
        cat_stats["credit_amount"] = round(cat_stats["credit_amount"], 2)
        cat_stats["debit_amount"] = round(cat_stats["debit_amount"], 2)
    
    return stats
