# FRIE Working Demo -- Data Requirements & Acquisition Plan

Analysis and design only. No application, frontend, backend, model,
dataset, scoring, contract, or behaviour changes were made. All feature
names match `backend/models/frie_model_config_v2.json` exactly (98 unique
features: 86 numeric + 12 categorical; target `frie_score`). Class
memberships below were verified programmatically against that contract:
USER 18/18, DERIVED 16/16, DOCUMENT 64 (computed), 18 + 64 + 16 = 98;
credit-information 49/49; historical-transaction 25/25.

## 1. Executive Summary

The future Working Demo must assemble the exact 98-feature vector before
`POST /predict` can be called, because the current contract rejects any
incomplete request with HTTP 422 and forbids silent defaults. Verified
split: **18 direct user-input features** (profile form), **64
document-derived features** (parsed records), **16 derived features**
(deterministic formulas). Documents needed: salary/income proof, bank
statements (12-month), credit report plus loan-application record,
insurance policies with premium history, and investment holding
statements. Transaction parsing is required for 25 history features;
49 features depend on credit information. The single biggest blocker is
realistic multi-record credit history (bureau tradelines, installment,
card, POS, and previous-application histories cannot be OCR'd from a
single statement and have no live integration). The recommended next
phase is the database plus authentication foundation, followed by the
profile/manual-input layer, before any document work begins.

## 2. Direct User Input Requirements

Only the 18 USER-class features belong on a profile form (never a
98-field form). "Direct or Derived" marks whether the form value is used
as-is or transformed; "Additional Processing" names that step.

| Feature | Data Type | User Question / UI Field | Example Input | Source | Direct or Derived | Mandatory | Additional Processing | Missing-Data Behaviour |
|---|---|---|---|---|---|---|---|---|
| gender | categorical | Gender (dropdown: F / M) | F | user profile | Direct | Yes | Map to training level | Reject record (422) |
| age_years | numeric | Date of birth (date picker) | 1993-04-12 | user profile | Derived | Yes | `age = -days_since_birth / 365.25` | Reject record (422) |
| children_count | numeric | Number of children (stepper) | 1 | user profile | Direct | Yes | Integer check | Reject record (422) |
| family_size | numeric | Family members (stepper) | 4 | user profile | Direct | Yes | Integer check | Reject record (422) |
| family_status | categorical | Marital status (dropdown, 5 levels) | Married | user profile | Direct | Yes | Map to training level | Reject record (422) |
| education_level | categorical | Highest education (dropdown, 4 levels) | Higher education | user profile | Direct | Yes | Map to training level | Reject record (422) |
| housing_type | categorical | Housing situation (dropdown, 4 levels) | House / apartment | user profile | Direct | Yes | Map to training level | Reject record (422) |
| owns_car | categorical | Do you own a car? (Y / N) | Y | user profile | Direct | Yes | Map to training level | Reject record (422) |
| owns_property | categorical | Do you own property? (Y / N) | N | user profile | Direct | Yes | Map to training level | Reject record (422) |
| income_type | categorical | Income category (dropdown, 4 levels) | Working | user profile | Direct | Yes | Map to training level | Reject record (422) |
| occupation | categorical | Occupation (dropdown, 15 levels) | Laborers | user profile | Direct | Yes | Map to training level; also feeds `occupation_band` lookup | Reject record (422) |
| organization_type | categorical | Employer type (dropdown) | Government | user profile | Direct | Yes | Map to training level | Reject record (422) |
| contract_type | categorical | Loan type applying for (Cash / Revolving) | Cash loans | loan application | Direct | Yes | Map to training level | Reject record (422) |
| city_tier | categorical | City of residence (city -> tier lookup) | Pune -> Tier_2 | user profile + Census tier table | Derived | Yes | City-to-tier mapping (`Tier_1/2/3`) | Reject record (422) |
| occupation_band | categorical | Derived from occupation (read-only display) | Salaried | occupation + PLFS band table | Derived | Yes | Occupation-to-band mapping | Reject record (422) |
| indian_household_size | numeric | Household size (defaults from family size) | 4 | user profile | Derived | Yes | `clip(family_size + variation, 1, 10)` | Reject record (422) |
| monthly_income | numeric | Stated monthly income (currency input) | 225000 | user profile, verified by salary slip | Direct | Yes | Positive-value check | Reject record (422) |
| employment_years | numeric | Employment start date (date picker) | 2018-06-01 | user profile | Derived | Yes | `years = -days_employed / 365.25`; unknown-code rule preserved | Reject record (422) |

Transform relationships shown above: date of birth -> `age_years`;
occupation -> `occupation_band`; city -> `city_tier`; family size ->
`indian_household_size`; employment start -> `employment_years`. No
formula is changed; these mirror the research derivations.

## 3. Document Requirements

Only document classes supported by the Phase 1 provenance are listed.
"User Confirmation" means the demo shows extracted values for review
before they enter the feature vector.

| Document Type | Features Supported | Number of Features | Directly Extractable Features | Features Requiring Engineering | OCR Required? | Structured/Table Parsing Required? | Transaction Parsing Required? | User Confirmation Required? | Missing Document Behaviour |
|---|---|---|---|---|---|---|---|---|---|
| Salary / income document | `monthly_income` (verification of stated figure) | 1 | `monthly_income` | 0 | Yes (income figure) | No | No | Yes | Stated income usable only as unverified demo input; record flagged accordingly |
| Bank statement (12-month) | 7 expense categories, `monthly_savings`, `savings_balance`, `upi_spending`, `upi_transaction_count`, 12-month net-flow series | 11 + series inputs for 4 cash-flow derivations | `savings_balance` (balance record) | 10 + 4 derived series stats | Yes (balances, UPI labels) | Yes (statement tables) | Yes (categorization, UPI aggregation, monthly netting) | Yes | Record cannot be scored; no estimation fallback without a documented rule |
| Credit report + loan application record | Current loan fields (3), bureau aggregates (10), installment aggregates + ratios (10), previous-application aggregates (7), card aggregates (9), POS aggregates (6), 4 credit ratios | 49 | `current_credit_amount`, `current_loan_annuity`, `goods_price` | 46 (all aggregates and ratios) | No (structured records required; a PDF alone is insufficient for tradeline histories) | Yes | Yes for installment/card/POS histories | Yes | Record cannot be scored; history must never be fabricated |
| Insurance document (policies + premium history) | `health_insurance`, `life_insurance`, `insurance_premium`, `insurance_payment_consistency` | 4 | holdings, premium amount | `insurance_payment_consistency` (12-period ratio) | Yes (policy fields, premium schedule) | Yes (payment schedule) | No | Yes | Record cannot be scored; no-holding needs a documented rule, never silent zero |
| Investment document (FD/RD/SIP/MF/PPF/NPS statements) | `fd_amount`, `rd_contribution`, `sip_contribution`, `mutual_fund_balance`, `ppf_contribution`, `nps_contribution` | 6 | All 6 amounts/balances | 0 | Yes (statement amounts) | Yes (holding tables) | No | Yes | Record cannot be scored; no-holding needs a documented rule, never silent zero |

Salary/income proof is the least load-bearing (verification only); the
credit-report family (49 features) is the most load-bearing and the least
obtainable from ordinary OCR.

## 4. Bank Statement Data Flow

Covered features: `food_expense`, `rent_expense`, `education_expense`,
`healthcare_expense`, `transport_expense`, `utility_expense`,
`discretionary_expense`, `monthly_savings`, `savings_balance`,
`upi_spending`, `upi_transaction_count`, `cash_flow_mean`,
`cash_flow_std`, `cash_flow_min`, `cash_flow_negative_months`.

Transformation implemented by the future pipeline:

Raw bank statement
-> transaction records (dated, signed amounts, counterparty/labels)
-> transaction categorization (7 expense classes + UPI/digital flags)
-> monthly aggregation (per-class monthly sums, UPI sums/counts,
   monthly net flow = income - expenses - commitments)
-> FRIE features (category totals, UPI totals, savings/balance reads,
   12-month series statistics).

Per-feature requirements:

A. Individual transaction records required: all 7 expense categories,
   `upi_spending`, `upi_transaction_count`, `monthly_savings`
   (inflow-minus-outflow), and every input to the net-flow series.
B. Monthly aggregation required: the same set, plus
   `synthetic_total_expense` (sum of the 7) and `digital_payment_ratio`.
C. 12-month history required: `cash_flow_mean`, `cash_flow_std`,
   `cash_flow_min`, `cash_flow_negative_months`
   (plus `insurance_payment_consistency`, which needs a 12-period
   premium schedule rather than bank data).
D. Derived calculations: `synthetic_total_expense` (sum),
   `digital_payment_ratio` (UPI share), the four cash-flow statistics,
   and (outside statements) `savings_rate` from savings and income.

OCR/text extraction (reading balances, labels, amounts off statement
pages) is distinct from transaction parsing (classifying lines,
aggregating by month/category, netting flows). No OCR capability for
understanding transactions is claimed; parsing is a separate,
deterministic engineering stage over extracted records.

## 5. Credit Information Data Flow

Groups, sources, and why OCR alone is insufficient:

- **Current loan/application (3: `current_credit_amount`,
  `current_loan_annuity`, `goods_price`).** Source: loan application
  record. Raw needs: sanctioned amount, annuity, goods price. No
  aggregation. OCR of an application form could suffice, but the values
  must come from the actual application, not estimates.
- **Bureau aggregates (10).** Source: bureau tradeline records.
  Raw needs: per-tradeline status, credit/debt/limit/overdue amounts,
  overdue days, prolongation counts. Aggregation: per-customer sums and
  counts. OCR alone is insufficient: this is multi-record tradeline
  history, realistically requiring structured bureau data or an
  Account-Aggregator-style feed.
- **Installment repayment history (10).** Source: installment ledger
  (`AMT_INSTALMENT`/`AMT_PAYMENT`/scheduled vs paid dates). Raw needs:
  every scheduled instalment with paid dates/amounts. Aggregation:
  counts, sums, delay statistics, then the two ratios. OCR alone is
  insufficient for the same multi-record reason.
- **Previous applications (7).** Source: previous-application records
  with contract statuses and amounts. Aggregation: counts by status,
  sums, means. OCR alone is insufficient.
- **Credit-card history (9).** Source: monthly card statements
  (balance, limit, drawings, payments, minimums, DPD flags).
  Aggregation: means, sums, maxima. OCR of one statement cannot supply
  a history; structured multi-month records are required.
- **POS cash history (6).** Source: POS finance records.
  Aggregation: counts, means, maxima. Same multi-record requirement.
- **Derived credit ratios (4: `current_dti`, `bureau_dti`,
  `previous_approval_ratio`, `bureau_overdue_ratio`).** Computed from
  the above plus income; no separate document, but every upstream value
  must be genuinely acquired first.

No claim is made that a generic credit-report PDF automatically yields
these fields; the provenance supports structured history records, and the
demo must either connect such a source or mark the credit block as a
controlled prototype input.

## 6. Insurance & Investment Data Flow

Document -> raw extracted values -> FRIE features:

- Health policy -> holding flag -> `health_insurance` (direct).
- Life policy -> holding flag -> `life_insurance` (direct).
- Premium schedule -> periodic amount -> `insurance_premium` (direct).
- Premium schedule, 12 periods -> paid-period ratio ->
  `insurance_payment_consistency` (history processing, not a document
  field).
- FD advice -> amount -> `fd_amount` (direct).
- RD statement -> monthly amount -> `rd_contribution` (direct).
- SIP statement -> monthly amount -> `sip_contribution` (direct).
- Mutual fund statement -> holdings value -> `mutual_fund_balance`
  (direct).
- PPF statement -> contribution -> `ppf_contribution` (direct).
- NPS statement -> contribution -> `nps_contribution` (direct).

Directly extractable: all amounts, balances, and holding flags.
Payment-history processing: `insurance_payment_consistency` only.
Aggregation: none beyond that ratio. Zero-holdings must follow a
documented rule in a future system, never a silent default.

## 7. Derived Feature Layer

All 16 derived features with exact existing formulas (unchanged):

| Feature | Upstream features | Exact formula | Upstream source | Processing | User sees intermediate? | Automatic? |
|---|---|---|---|---|---|---|
| `current_dti` | `current_loan_annuity`, `monthly_income` | annuity / income (NaN if income not positive) | loan record + stated income | division + guard | No | Yes |
| `bureau_dti` | `bureau_debt_amount`, `monthly_income` | debt / income (NaN if income not positive) | bureau aggregate + stated income | division + guard | No | Yes |
| `previous_approval_ratio` | `previous_approved_count`, `previous_application_count` | approved / count (NaN if zero) | previous-application aggregates | division + guard | No | Yes |
| `bureau_overdue_ratio` | `bureau_overdue_amount`, `bureau_credit_amount` | overdue / credit (NaN if zero) | bureau aggregates | division + guard | No | Yes |
| `on_time_payment_ratio` | `total_on_time_payments`, `total_installments` | on-time / total (NaN if zero) | installment aggregates | division + guard | No | Yes |
| `payment_coverage_ratio` | `total_amount_paid`, `total_amount_due` | paid / due (NaN if zero) | installment aggregates | division + guard | No | Yes |
| `synthetic_total_expense` | 7 expense categories | sum of the seven | statement categorization | summation | No | Yes |
| `synthetic_spending_ratio` | `synthetic_total_expense`, `monthly_income` | expense / income (research clips [0.40, 0.88]) | derived + stated income | division | No | Yes |
| `synthetic_total_emi` | `current_loan_annuity`, `monthly_income` | min(annuity, 0.50 x income) | loan record + stated income | min + cap | No | Yes |
| `available_surplus` | `monthly_income`, `synthetic_total_expense`, `synthetic_total_emi` | max(income - expense - emi, 0) | mixed upstream | arithmetic + floor | No | Yes |
| `savings_rate` | `monthly_savings`, `monthly_income` | clip(savings / income, 0, 0.80) | statement-derived + stated income | division + clip | No | Yes |
| `digital_payment_ratio` | `upi_spending`, `synthetic_total_expense` | upi / expense (0 if zero) | statement-derived | division + guard | No | Yes |
| `cash_flow_mean` | 12-month net-flow series | mean of monthly (income - expense - commitments) | statement series | series statistics | No | Yes |
| `cash_flow_std` | 12-month net-flow series | standard deviation of the series | statement series | series statistics | No | Yes |
| `cash_flow_min` | 12-month net-flow series | minimum of the series | statement series | series statistics | No | Yes |
| `cash_flow_negative_months` | 12-month net-flow series | count of months below zero | statement series | series statistics | No | Yes |

Conceptual layering: RAW INPUTS -> SOURCE-SPECIFIC EXTRACTION ->
NORMALIZATION (units, levels, guards) -> FEATURE ENGINEERING
(aggregations above) -> DERIVED FEATURES (this table) -> FINAL
98-FEATURE VECTOR (strict validation).

## 8. Complete 98-Feature Source Matrix

Conventions: Type N = numeric, C = categorical. Foundation (F) =
Home Credit layer (64 features); Synthetic (S) = Indian layer (34).
User/Document/OCR/Txn/Eng are Yes/No flags; exactly the 18 USER rows
have User=Yes, exactly the 64 DOCUMENT rows have Document=Yes, and the
16 derived rows have both No with Upstream listed. Mandatory is Yes for
all 98 (missing -> HTTP 422, no zero-fill). Final Model Input is Yes
for all 98. Secondary sources name verification or fallback origins.

| Feature | Type | F/S | Primary Source | Secondary Source | Acquisition Method | User Input? | Document Input? | OCR? | Transaction Parsing? | Feature Engineering? | Upstream Features | Mandatory? | Missing-Data Behaviour | Final Model Input? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gender | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | CODE_GENDER | Yes | Reject 422 | Yes |
| age_years | N | F | user profile form | application record | date of birth + conversion | Yes | No | No | No | Yes | date of birth | Yes | Reject 422 | Yes |
| children_count | N | F | user profile form | application record | form stepper | Yes | No | No | No | No | CNT_CHILDREN | Yes | Reject 422 | Yes |
| family_size | N | F | user profile form | application record | form stepper | Yes | No | No | No | No | CNT_FAM_MEMBERS | Yes | Reject 422 | Yes |
| family_status | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | NAME_FAMILY_STATUS | Yes | Reject 422 | Yes |
| education_level | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | NAME_EDUCATION_TYPE | Yes | Reject 422 | Yes |
| housing_type | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | NAME_HOUSING_TYPE | Yes | Reject 422 | Yes |
| owns_car | C | F | user profile form | application record | form Y/N | Yes | No | No | No | No | FLAG_OWN_CAR | Yes | Reject 422 | Yes |
| owns_property | C | F | user profile form | application record | form Y/N | Yes | No | No | No | No | FLAG_OWN_REALTY | Yes | Reject 422 | Yes |
| income_type | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | NAME_INCOME_TYPE | Yes | Reject 422 | Yes |
| occupation | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | OCCUPATION_TYPE | Yes | Reject 422 | Yes |
| organization_type | C | F | user profile form | application record | form dropdown | Yes | No | No | No | No | ORGANIZATION_TYPE | Yes | Reject 422 | Yes |
| contract_type | C | F | loan application | application record | loan-type choice | Yes | No | No | No | No | NAME_CONTRACT_TYPE | Yes | Reject 422 | Yes |
| monthly_income | N | F | user profile (stated) | salary slip verification | currency input + slip check | Yes | No | Yes | No | No | AMT_INCOME_TOTAL | Yes | Reject 422 | Yes |
| employment_years | N | F | user profile form | application record | start-date + conversion | Yes | No | No | No | Yes | employment start date | Yes | Reject 422 | Yes |
| current_credit_amount | N | F | loan application record | credit report | structured record read | No | Yes | No | No | No | AMT_CREDIT | Yes | Reject 422 | Yes |
| current_loan_annuity | N | F | loan application record | credit report | structured record read | No | Yes | No | No | No | AMT_ANNUITY | Yes | Reject 422 | Yes |
| goods_price | N | F | loan application record | credit report | structured record read | No | Yes | No | No | No | AMT_GOODS_PRICE | Yes | Reject 422 | Yes |
| current_dti | N | F | derived | -- | formula | No | No | No | No | Yes | current_loan_annuity, monthly_income | Yes | Reject 422 | Yes |
| bureau_dti | N | F | derived | -- | formula | No | No | No | No | Yes | bureau_debt_amount, monthly_income | Yes | Reject 422 | Yes |
| previous_approval_ratio | N | F | derived | -- | formula | No | No | No | No | Yes | previous_approved_count, previous_application_count | Yes | Reject 422 | Yes |
| bureau_overdue_ratio | N | F | derived | -- | formula | No | No | No | No | Yes | bureau_overdue_amount, bureau_credit_amount | Yes | Reject 422 | Yes |
| bureau_account_count | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| active_credit_count | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| closed_credit_count | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| bureau_credit_amount | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| bureau_debt_amount | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| bureau_credit_limit | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| bureau_overdue_amount | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| bureau_overdue_days | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| bureau_overdue_account_count | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| credit_prolongation_count | N | F | credit report | bureau API (future) | tradeline aggregation | No | Yes | No | No | Yes | bureau tradelines | Yes | Reject 422 | Yes |
| total_installments | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| total_amount_due | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| total_amount_paid | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| total_late_payments | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| total_on_time_payments | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| average_payment_delay | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| total_payment_delay_days | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| payment_difference | N | F | credit report | repayment ledger | installment aggregation | No | Yes | No | Yes | Yes | installment records | Yes | Reject 422 | Yes |
| on_time_payment_ratio | N | F | derived | -- | formula | No | No | No | No | Yes | total_on_time_payments, total_installments | Yes | Reject 422 | Yes |
| payment_coverage_ratio | N | F | derived | -- | formula | No | No | No | No | Yes | total_amount_paid, total_amount_due | Yes | Reject 422 | Yes |
| previous_application_count | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| previous_approved_count | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| previous_refused_count | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| previous_credit_amount | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| previous_avg_credit | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| previous_avg_annuity | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| previous_avg_down_payment | N | F | credit report | bureau API (future) | application aggregation | No | Yes | No | No | Yes | previous-application records | Yes | Reject 422 | Yes |
| avg_credit_card_balance | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| max_credit_card_balance | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| avg_credit_limit | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| total_card_drawings | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| total_card_payments | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| avg_minimum_payment | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| avg_credit_utilisation | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| max_card_dpd | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| max_card_dpd_default | N | F | credit report | card statements | card aggregation | No | Yes | No | Yes | Yes | card monthly records | Yes | Reject 422 | Yes |
| pos_account_records | N | F | credit report | POS records | POS aggregation | No | Yes | No | Yes | Yes | POS cash records | Yes | Reject 422 | Yes |
| avg_pos_installments | N | F | credit report | POS records | POS aggregation | No | Yes | No | Yes | Yes | POS cash records | Yes | Reject 422 | Yes |
| avg_future_installments | N | F | credit report | POS records | POS aggregation | No | Yes | No | Yes | Yes | POS cash records | Yes | Reject 422 | Yes |
| pos_dpd_count | N | F | credit report | POS records | POS aggregation | No | Yes | No | Yes | Yes | POS cash records | Yes | Reject 422 | Yes |
| max_pos_dpd | N | F | credit report | POS records | POS aggregation | No | Yes | No | Yes | Yes | POS cash records | Yes | Reject 422 | Yes |
| max_pos_dpd_default | N | F | credit report | POS records | POS aggregation | No | Yes | No | Yes | Yes | POS cash records | Yes | Reject 422 | Yes |
| city_tier | C | S | user profile (city) | Census tier table | city-to-tier lookup | Yes | No | No | No | Yes | city of residence | Yes | Reject 422 | Yes |
| occupation_band | C | S | user profile (occupation) | PLFS band table | occupation-to-band lookup | Yes | No | No | No | Yes | occupation | Yes | Reject 422 | Yes |
| indian_household_size | N | S | user profile (family) | -- | household adjustment | Yes | No | No | No | Yes | family_size | Yes | Reject 422 | Yes |
| food_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | food transactions | Yes | Reject 422 | Yes |
| rent_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | rent transactions | Yes | Reject 422 | Yes |
| education_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | education transactions | Yes | Reject 422 | Yes |
| healthcare_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | healthcare transactions | Yes | Reject 422 | Yes |
| transport_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | transport transactions | Yes | Reject 422 | Yes |
| utility_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | utility transactions | Yes | Reject 422 | Yes |
| discretionary_expense | N | S | bank statement | user estimate (fallback) | transaction categorization | No | Yes | No | Yes | Yes | discretionary transactions | Yes | Reject 422 | Yes |
| synthetic_total_expense | N | S | derived | -- | summation | No | No | No | No | Yes | 7 expense categories | Yes | Reject 422 | Yes |
| synthetic_spending_ratio | N | S | derived | -- | division | No | No | No | No | Yes | synthetic_total_expense, monthly_income | Yes | Reject 422 | Yes |
| synthetic_total_emi | N | S | derived | loan schedule | capped formula | No | No | No | No | Yes | current_loan_annuity, monthly_income | Yes | Reject 422 | Yes |
| available_surplus | N | S | derived | -- | arithmetic + floor | No | No | No | No | Yes | monthly_income, synthetic_total_expense, synthetic_total_emi | Yes | Reject 422 | Yes |
| monthly_savings | N | S | bank statement | -- | flow measurement | No | Yes | No | Yes | Yes | statement flows, available_surplus | Yes | Reject 422 | Yes |
| savings_rate | N | S | derived | -- | division + clip | No | No | No | No | Yes | monthly_savings, monthly_income | Yes | Reject 422 | Yes |
| savings_balance | N | S | bank statement | -- | balance read | No | Yes | Yes | No | No | account balance record | Yes | Reject 422 | Yes |
| fd_amount | N | S | investment document | -- | stated amount | No | Yes | Yes | No | No | FD document | Yes | Reject 422 | Yes |
| rd_contribution | N | S | investment document | -- | stated amount | No | Yes | Yes | No | No | RD document | Yes | Reject 422 | Yes |
| upi_spending | N | S | bank statement | -- | UPI aggregation | No | Yes | No | Yes | Yes | UPI transactions | Yes | Reject 422 | Yes |
| upi_transaction_count | N | S | bank statement | -- | UPI counting | No | Yes | No | Yes | Yes | UPI transactions | Yes | Reject 422 | Yes |
| digital_payment_ratio | N | S | derived | -- | division | No | No | No | No | Yes | upi_spending, synthetic_total_expense | Yes | Reject 422 | Yes |
| sip_contribution | N | S | investment document | -- | stated amount | No | Yes | Yes | No | No | SIP document | Yes | Reject 422 | Yes |
| mutual_fund_balance | N | S | investment document | -- | stated balance | No | Yes | Yes | No | No | mutual fund document | Yes | Reject 422 | Yes |
| ppf_contribution | N | S | investment document | -- | stated amount | No | Yes | Yes | No | No | PPF document | Yes | Reject 422 | Yes |
| nps_contribution | N | S | investment document | -- | stated amount | No | Yes | Yes | No | No | NPS document | Yes | Reject 422 | Yes |
| health_insurance | N | S | insurance document | -- | stated holding | No | Yes | Yes | No | No | health policy | Yes | Reject 422 | Yes |
| life_insurance | N | S | insurance document | -- | stated holding | No | Yes | Yes | No | No | life policy | Yes | Reject 422 | Yes |
| insurance_premium | N | S | insurance document | -- | stated premium | No | Yes | Yes | No | No | insurance documents | Yes | Reject 422 | Yes |
| insurance_payment_consistency | N | S | insurance document | -- | 12-period ratio | No | Yes | Yes | No | Yes | premium payment history | Yes | Reject 422 | Yes |
| cash_flow_mean | N | S | derived (bank series) | -- | series statistics | No | No | No | Yes | Yes | 12-month net-flow series | Yes | Reject 422 | Yes |
| cash_flow_std | N | S | derived (bank series) | -- | series statistics | No | No | No | Yes | Yes | 12-month net-flow series | Yes | Reject 422 | Yes |
| cash_flow_min | N | S | derived (bank series) | -- | series statistics | No | No | No | Yes | Yes | 12-month net-flow series | Yes | Reject 422 | Yes |
| cash_flow_negative_months | N | S | derived (bank series) | -- | series statistics | No | No | No | Yes | Yes | 12-month net-flow series | Yes | Reject 422 | Yes |

## 9. Data Readiness Logic

Conceptual statuses for the future UI (not implemented):

- **NOT READY:** fewer than 98 valid contracted values are assembled,
  any value fails type/range/level checks, or a required document for a
  mandatory block is missing. Scoring is disabled.
- **PARTIALLY READY:** at least one complete acquisition block is valid
  (for example profile + derived profile fields) but the full vector is
  incomplete. The UI shows per-block progress; scoring stays disabled.
- **READY FOR SCORING:** all 98 model features hold valid values matching
  the current contract (86 finite numerics, 12 known-level categoricals,
  no extras, no target). Only this status enables `POST /predict`.

No silent filling is permitted at any status: unavailable financial
information blocks readiness; arbitrary mean imputation is forbidden;
credit history must never be fabricated. A future "documented fallback"
(e.g., a verified no-holding attestation) would be an explicit,
auditable input -- not an imputation.

## 10. Working Demo User Journey

STEP 1 -- Register / Login. User action: create account / sign in.
System: authenticate (future real auth). Data: session identity.
Dependency: Phase 2 backend store.

STEP 2 -- Complete Profile. User action: fill the 18-field profile form
(Section 2). System: validate types, map lookups (city tier, band).
Data: 18 USER features. Dependency: login.

STEP 3 -- Provide User Inputs. User action: confirm derived profile
values (age, employment years, household size). System: compute
conversions with the documented rules. Data: completed profile block.
Dependency: Step 2.

STEP 4 -- Upload Documents. User action: upload salary slip, 12-month
bank statements, credit report + loan record, insurance policies with
premium history, investment statements. System: store with source
metadata. Data: raw document set. Dependency: profile.

STEP 5 -- OCR / Extraction. User action: none (or resolve flagged
fields). System: extract balances, amounts, holdings, schedules, and
statement tables. Data: extracted records with confidence flags.
Dependency: Step 4.

STEP 6 -- Review Extracted Information. User action: confirm or correct
every extracted value. System: present per-document review screens.
Data: confirmed source records. Dependency: Step 5.

STEP 7 -- Transaction Parsing / Feature Engineering. User action: none.
System: categorize transactions, aggregate histories, apply the 16
derivations. Data: full 98-feature vector with per-feature provenance.
Dependency: Step 6.

STEP 8 -- 98 Features Ready. User action: review readiness checklist.
System: validate against the strict contract; status becomes READY FOR
SCORING only on full validity. Data: validated vector. Dependency:
Step 7.

STEP 9 -- Calculate FRIE Score. User action: request scoring. System:
`POST /predict` with the 98 features (V2 pipeline). Data: `frie_score`
+ backend `reliability_level`. Dependency: Step 8.

STEP 10 -- View 8 FRIE Indicators. User action: open the breakdown.
System: display the scoring-engine indicator profile for the record.
Data: 8 indicator values with the model-prediction distinction labeled.
Dependency: Step 9.

STEP 11 -- View Explainability. User action: open explanations. System:
present recorded global importance and (future) per-request SHAP
attributions as model-behaviour descriptions only. Dependency: Step 9.

## 11. Prototype vs Production Boundary

A. CURRENTLY IMPLEMENTED (verified in repository): React + Vite
Individual demo; FastAPI `/health` + `/predict` with strict 98-feature
validation; saved V2 pipeline loaded at startup; dev-only dataset
record access; dataset customer selector; model-generated score display
with backend reliability level; indicator breakdown from the scored
dataset row; recorded SHAP findings; 15 pytest tests; perf probe;
bundle-verified production build.

B. TO BE IMPLEMENTED FOR THE WORKING DEMO: database plus real
authentication; customer profile and manual-input layer; document upload
with source metadata; OCR plus document extraction with review;
statement transaction parsing; history aggregation and the 16
derivations; readiness-gated prediction UI; per-request SHAP display.

C. FUTURE / PRODUCTION-LEVEL CAPABILITY: real banking integrations,
Account Aggregator connectivity, live financial APIs, production
identity verification, production document storage, production-grade
authentication and security review, and any validation of FRIE scores
against real-world financial outcomes.

## 12. Demo Data Strategy

- Genuinely user-enterable: the 18 profile fields (Section 2) typed by
  the demo user into the future form.
- Synthetic/demo documents: prepared salary slip, 12-month synthetic
  statements, and policy/holding statements mirroring the research
  distributions, each visibly watermarked or labelled as demo data.
- Prototype OCR: run only over those prepared demo documents, with
  extracted values shown for review before use.
- Deterministic engineering: the 16 derivations computed by the
  documented formulas over confirmed inputs.
- Credit history: the sensitive block. Without a live bureau feed, use
  a controlled prototype credit-history source (clearly labelled demo
  data, e.g., the existing research aggregates for a synthetic
  individual) -- never presented as a real bureau pull and never
  fabricated per-field by hand.
- Explicitly synthetic at all times: expense category values, UPI flows,
  holdings, and any credit-history block, until real sources exist. No
  real personal financial data is introduced at any stage.

## 13. Future Phase Dependencies

PHASE 2 -- Database + Authentication. Inputs: user credentials, consent
records. Outputs: sessions, customer identity store. Dependencies:
schema design, password handling review. Risks: auth scope creep;
keep demo-grade initially and label it.

PHASE 3 -- Customer Profile / Manual Inputs. Inputs: Section 2 field
spec. Outputs: validated 18-feature profile block. Dependencies:
Phase 2. Risks: categorical level drift vs training levels; enforce
exact-level dropdowns.

PHASE 4 -- Document Upload. Inputs: the five document classes.
Outputs: stored documents with source metadata. Dependencies: Phase 2
storage. Risks: accepting unparseable scans; require review flags.

PHASE 5 -- OCR + Document Extraction. Inputs: stored documents.
Outputs: extracted records with confidence. Dependencies: Phase 4.
Risks: over-trusting OCR; every value needs review before use.

PHASE 6 -- Feature Engineering / 98 Features. Inputs: confirmed
records. Outputs: validated 98-vector with provenance. Dependencies:
Phases 3-5. Risks: history gaps (the credit-history blocker); no
silent defaults allowed, so gaps halt readiness by design.

PHASE 7 -- Prediction. Inputs: validated vector. Outputs: score +
level via existing backend. Dependencies: Phase 6. Risks: none
structural (backend already serves V2); keep contract frozen.

PHASE 8 -- Explainability / SHAP. Inputs: prediction + features.
Outputs: per-request attributions display. Dependencies: Phase 7.
Risks: presenting attributions as causal advice; keep the
model-behaviour wording.

PHASE 9 -- End-to-End Dashboard. Inputs: all upstream outputs.
Outputs: unified demo UI. Dependencies: Phases 2-8. Risks: reintroducing
mock sections; keep the no-fake-data rule.

PHASE 10 -- Integration + Error Handling. Inputs: full flow.
Dependencies: Phase 9. Risks: backend-down, malformed, and partial-data
paths must all show controlled states (patterns already exist).

PHASE 11 -- Full Testing. Inputs: all phases. Outputs: extended suite
plus updated NFR evidence. Dependencies: Phase 10. Risks: none
structural.

PHASE 12 -- Demo Hardening. Inputs: test results. Outputs: demo script,
reset procedure, labelled demo dataset. Dependencies: Phase 11. Risks:
last-minute scope additions; freeze scope early.

## 14. Risks / Blockers

1. **Credit-history acquisition (biggest blocker):** 49 features need
   credit information and 25 need multi-record transaction histories
   that cannot be OCR'd from a single statement and have no live
   integration. Without a controlled prototype history source, the demo
   cannot honestly score a user-supplied individual end to end.
2. **Twelve-month series dependency:** cash-flow statistics (and the
   premium-consistency ratio) need full trailing histories; partial
   histories must block readiness, not trigger estimation.
3. **Categorical drift:** free-text occupations, cities, or statuses
   outside training levels are ignored by the encoder; the UI must use
   exact-level dropdowns to avoid silent information loss.
4. **No-holding ambiguity:** investment/insurance zeros are ambiguous
   between "no holding" and "unknown"; a future documented attestation
   rule is required before these can be optional.
5. **Scope creep into production claims:** banking integrations,
   Account Aggregator, and outcome validation are explicitly future;
   the demo must keep prototype labelling to stay academically honest.

## 15. Final Verification

Counts verified programmatically against
`backend/models/frie_model_config_v2.json` (all membership lists in
this plan match the live contract exactly):

- Total model features reviewed: **98**
- Numeric features: **86**
- Categorical features: **12**
- Direct user-input features: **18**
- Document-derived features: **64**
- Derived features: **16**
- Foundation features: **64**
- Indian synthetic-layer features: **34**
- Reconciliation: 18 + 64 + 16 = **98**; 64 + 34 = **98**; matrix rows
  below total **98** unique contracted features.
- Features requiring credit information: **49** (membership verified).
- Features requiring historical transaction information: **25**
  (membership verified; 17 further bureau/previous-application features
  need multi-record credit history and are counted separately).
- Features requiring 12-month history: **5** (`cash_flow_mean`,
  `cash_flow_std`, `cash_flow_min`, `cash_flow_negative_months`,
  `insurance_payment_consistency`).
- Cannot realistically be acquired in the planned academic demo without
  a controlled prototype source: the 49-credit-information block and,
  within it, the 25 transaction-history features (see Risk 1).
- Unresolved ambiguity: the exact real-world mapping of
  `monthly_income` to salary-slip pay-cycle figures needs a payroll
  convention decision in a future phase; the research code maps stated
  income directly.
