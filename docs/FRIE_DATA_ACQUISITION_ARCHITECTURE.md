# FRIE Data Acquisition Architecture

Design-only document. Nothing is implemented here and no application,
model, scoring, dataset, or contract changes were made. The acquisition
classes below are assigned per feature in
`docs/FRIE_98_FEATURE_PROVENANCE.md`; all counts here are verified by
enumerating those assignments (primary classes sum to 98).

## Planned flow

User Input
  (profile form: identity, demographics, employment context, stated income)
  +
Documents
  (salary slip, bank statements, credit report, insurance documents,
  investment documents, loan application record)
  +
OCR / Text Extraction
  (machine-readable fields from salary slips, statements, policy and
  holding documents; bureau/application records arrive structured)
  +
Transaction Parsing
  (statement transaction categorization into the seven expense classes
  plus UPI/digital flows; monthly net-flow series construction)
  +
Feature Engineering
  (history aggregation over bureau/installment/card/POS/previous-application
  records; ratio, total, and cash-flow derivations per the documented
  formulas; city/band lookups; categorical level normalization to the
  training levels)
  +
98-Feature Validation
  (strict contract: 86 numeric finite values + 12 non-empty categoricals;
  extras rejected; `frie_score` rejected as input; missing values rejected --
  never zero-filled)
  +
XGBoost
  (saved V2 preprocessing-plus-regression pipeline, loaded once at startup)
  +
FRIE Score
  (`frie_score` with backend-authoritative `reliability_level`)
  +
SHAP Explanation
  (offline global importance today; per-request local attributions are
  future scope and must never be presented as causal or externally
  validated findings)

## Acquisition classes and verified counts

Primary class rule: each of the 98 features is assigned to exactly one of
USER (answerable on a form with no document), DOCUMENT (requires parsing a
stated document class), or DERIVED (computed deterministically from sibling
features by a stated formula).

### Direct user-input features: 18

G1 profile fields (13): `gender`, `age_years` (from date of birth),
`children_count`, `family_size`, `family_status`, `education_level`,
`housing_type`, `owns_car`, `owns_property`, `income_type`, `occupation`,
`organization_type`, `contract_type`; plus G8 context (3): `city_tier`,
`occupation_band`, `indian_household_size`; plus stated
`monthly_income` (verifiable via salary slip) and `employment_years`
(from employment start date).

### Document-derived features: 64

- Credit report / loan application records (43): `current_credit_amount`,
  `current_loan_annuity`, `goods_price`; all 10 bureau aggregates; the 8
  transaction-level installment aggregates; all 7 previous-application
  aggregates; all 9 credit-card aggregates; all 6 POS aggregates.
- Bank statements (11): the 7 expense categories, `monthly_savings`,
  `savings_balance`, `upi_spending`, `upi_transaction_count`.
- Insurance documents (4): `health_insurance`, `life_insurance`,
  `insurance_premium`, `insurance_payment_consistency`.
- Investment documents (6): `fd_amount`, `rd_contribution`,
  `sip_contribution`, `mutual_fund_balance`, `ppf_contribution`,
  `nps_contribution`.

### Derived features: 16

`current_dti`, `bureau_dti`, `previous_approval_ratio`,
`bureau_overdue_ratio`, `on_time_payment_ratio`,
`payment_coverage_ratio`, `synthetic_total_expense`,
`synthetic_spending_ratio`, `synthetic_total_emi`,
`available_surplus`, `savings_rate`, `digital_payment_ratio`,
`cash_flow_mean`, `cash_flow_std`, `cash_flow_min`,
`cash_flow_negative_months`. Exact formulas are documented per feature
in the provenance file.

Check: 18 + 64 + 16 = 98.

### Features requiring credit information: 49

All features whose value depends on credit-report, loan-application, or
repayment-history data: the 10 bureau, 10 installment, 7
previous-application, 9 credit-card, and 6 POS features (42), plus the 3
current-loan fields and the 4 credit-dependent ratios (`current_dti`,
`bureau_dti`, `previous_approval_ratio`, `bureau_overdue_ratio`).

### Features requiring historical transaction information: 25

Features aggregated over multi-record transaction-level history: the 10
installment features (8 aggregates + 2 ratios derived from them), the 9
credit-card features, and the 6 POS features. A further 17 features
require multi-record credit history of a different kind (10 bureau
tradelines + 7 previous applications) and are counted separately to keep
the transaction definition strict.

## Stage-by-stage responsibilities (future build)

1. **User Input service:** collects the 18 USER features with type and
   range checks; never accepts document-derived values by hand without a
   verified-source flag.
2. **Document ingestion:** stores salary slips, statements, credit
   reports, insurance and investment documents with source metadata.
3. **OCR/text extraction:** converts document images/PDFs to fields;
   low-confidence extractions are flagged for review, never silently
   accepted.
4. **Transaction parsing:** categorizes statement lines into the expense
   taxonomy, aggregates UPI/digital flows, and builds the 12-month
   net-flow series.
5. **Feature engineering:** applies only the documented aggregation and
   derivation formulas; categorical outputs are normalized to training
   levels (unseen levels pass through to the encoder's ignore path).
6. **98-feature validation:** identical strictness to the current API
   (missing/unexpected/non-finite rejected; target rejected).
7. **Prediction:** unchanged saved V2 pipeline via the existing backend.
8. **Explanation:** recorded SHAP findings today; optional per-request
   attributions later, presented as model-behaviour descriptions only.

## Explicit non-goals for acquisition honesty

- No silent zero-fill or mean-fill at the API boundary, ever.
- No invented availability: a feature with no legitimate source stays
  unobtainable until a real source exists (e.g., full bureau history
  requires actual bureau access, not estimation).
- `frie_score` is an output and a training target only; it must never
  appear in any input payload.
- Nothing in these materials changes the current contract, model, dataset,
  scoring methodology, or demo behaviour.
