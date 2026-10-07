# FRIE 98-Feature Provenance

Analysis and design document. No application, model, scoring, dataset, or
contract changes were made. Every statement below is grounded in the actual
project files: `backend/models/frie_model_config_v2.json` (the 98-feature
contract: 86 numeric + 12 categorical), `D:/frie/output/home_credit_base.csv`
(the Home Credit foundation table), `D:/frie/02_generate_indian_synthetic.py`
(the Indian synthetic layer, including its `indian_columns` list),
`D:/frie/01_build_home_credit_base.py` (foundation aggregations),
`D:/frie/HomeCredit_columns_description.csv`, and observed value levels in
`D:/frie/Model Train/frie_ml_test.csv`.

## Provenance method

Each of the 98 contract features was looked up in `home_credit_base.csv`:

- **64 features exist as foundation columns** (origin: Home Credit
  `application_*`, `bureau`, `previous_application`, `installments_payments`,
  `credit_card_balance`, `POS_CASH_balance`, plus ratios derived from them
  in `01_build_home_credit_base.py`).
- **34 features exist only in the Indian synthetic layer** (exact match with
  the `indian_columns` list in `02_generate_indian_synthetic.py`).

## Global rules (apply to every feature below)

- **Mandatory:** Yes. All 98 features are required by `POST /predict`;
  any missing value is rejected with HTTP 422. The API performs no
  imputation and no zero-filling.
- **If unavailable:** In the current prototype the record cannot be scored
  (the dev selector lists only complete records). In a future input system
  the field must be collected from its stated source or covered by a
  documented, auditable fallback. Silent zero-fill is never acceptable.
- **Categorical mapping:** All 12 categorical features are one-hot encoded
  with `handle_unknown="ignore"`. Values must be sent using the training
  levels listed; unseen levels are ignored by the encoder (treated as
  all-zero for that variable), never erroring and never inventing a level.

## Group G1 -- Application identity and demographics (foundation, 13)

### `gender` -- categorical
- **Semantic meaning:** Applicant gender.
- **Possible source:** user profile/input (application form).
- **Directly extractable:** Yes, from the application record
  (`CODE_GENDER` renamed to `gender`).
- **Requires feature engineering:** No (rename only).
- **Derivation:** direct rename.
- **Upstream fields:** `CODE_GENDER`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `F`, `M`.

### `age_years` -- numeric
- **Semantic meaning:** Applicant age in years.
- **Possible source:** user profile/input (date of birth).
- **Directly extractable:** Yes, after unit conversion.
- **Requires feature engineering:** Yes, unit conversion only.
- **Derivation:** `age_years = -DAYS_BIRTH / 365.25`
  (`01_build_home_credit_base.py`).
- **Upstream fields:** date of birth.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect date of birth.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `children_count` -- numeric
- **Semantic meaning:** Number of applicant's children.
- **Possible source:** user profile/input (`CNT_CHILDREN` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `CNT_CHILDREN`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `family_size` -- numeric
- **Semantic meaning:** Applicant family size.
- **Possible source:** user profile/input (`CNT_FAM_MEMBERS` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `CNT_FAM_MEMBERS`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `family_status` -- categorical
- **Semantic meaning:** Applicant marital/family status.
- **Possible source:** user profile/input (`NAME_FAMILY_STATUS` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `NAME_FAMILY_STATUS`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `Civil marriage`,
  `Married`, `Separated`, `Single / not married`, `Widow`.

### `education_level` -- categorical
- **Semantic meaning:** Highest education attained.
- **Possible source:** user profile/input (`NAME_EDUCATION_TYPE` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `NAME_EDUCATION_TYPE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `Higher education`,
  `Incomplete higher`, `Lower secondary`, `Secondary / secondary special`.

### `housing_type` -- categorical
- **Semantic meaning:** Applicant housing situation.
- **Possible source:** user profile/input (`NAME_HOUSING_TYPE` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `NAME_HOUSING_TYPE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `House / apartment`,
  `Municipal apartment`, `Rented apartment`, `With parents`.

### `owns_car` -- categorical
- **Semantic meaning:** Whether the applicant owns a car.
- **Possible source:** user profile/input (`FLAG_OWN_CAR` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `FLAG_OWN_CAR`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `N`, `Y`.

### `owns_property` -- categorical
- **Semantic meaning:** Whether the applicant owns realty.
- **Possible source:** user profile/input (`FLAG_OWN_REALTY` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `FLAG_OWN_REALTY`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `N`, `Y`.

### `income_type` -- categorical
- **Semantic meaning:** Applicant income/employment category.
- **Possible source:** user profile/input (`NAME_INCOME_TYPE` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `NAME_INCOME_TYPE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `Commercial associate`,
  `Pensioner`, `State servant`, `Working`.

### `occupation` -- categorical
- **Semantic meaning:** Applicant occupation type.
- **Possible source:** user profile/input (`OCCUPATION_TYPE` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `OCCUPATION_TYPE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels include `Accountants`,
  `Cleaning staff`, `Cooking staff`, `Core staff`, `Drivers`,
  `High skill tech staff`, `Laborers`, `Low-skill Laborers`, `Managers`,
  `Medicine staff`, `Private service staff`, `Realty agents`,
  `Sales staff`, `Security staff`, `Waiters/barmen staff`.

### `organization_type` -- categorical
- **Semantic meaning:** Applicant employer organization type.
- **Possible source:** user profile/input (`ORGANIZATION_TYPE` renamed).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename.
- **Upstream fields:** `ORGANIZATION_TYPE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect on form.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels include `Agriculture`,
  `Bank`, `Business Entity Type 1/2/3`, `Government`, `Medicine`,
  `Military`, `Police`, `School`, `Self-employed`, `XNA` (33 levels total
  in test data).

### `contract_type` -- categorical
- **Semantic meaning:** Contract type of the current loan.
- **Possible source:** user profile/input (loan application choice;
  `NAME_CONTRACT_TYPE` of the application record).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct rename of the application record field.
- **Upstream fields:** `NAME_CONTRACT_TYPE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect at application time.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** Yes. Observed levels: `Cash loans`,
  `Revolving loans`.

## Group G2 -- Income, employment, loan and ratio fields (foundation, 9)

### `monthly_income` -- numeric
- **Semantic meaning:** Stated income figure used as monthly income.
- **Possible source:** user profile/input, verifiable via salary slip
  (research code maps `AMT_INCOME_TOTAL` to this field).
- **Directly extractable:** Yes, after rename.
- **Requires feature engineering:** No.
- **Derivation:** direct rename of `AMT_INCOME_TOTAL`.
- **Upstream fields:** stated income (`AMT_INCOME_TOTAL`).
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect stated income and verify
  against salary slip in a future system.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `employment_years` -- numeric
- **Semantic meaning:** Employment duration in years.
- **Possible source:** user profile/input (employment start date).
- **Directly extractable:** Yes, after unit conversion.
- **Requires feature engineering:** Yes, unit conversion plus anomaly rule.
- **Derivation:** `employment_years = -DAYS_EMPLOYED / 365.25`, with
  `NaN` when `DAYS_EMPLOYED > -1000` (the 365243 unknown-code convention).
- **Upstream fields:** employment start date.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect employment start date.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `current_credit_amount` -- numeric
- **Semantic meaning:** Credit amount of the current loan application.
- **Possible source:** loan application / credit report (`AMT_CREDIT`).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct application field.
- **Upstream fields:** `AMT_CREDIT`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect from loan application.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `current_loan_annuity` -- numeric
- **Semantic meaning:** Annuity (periodic payment) of the current loan.
- **Possible source:** loan application / credit report (`AMT_ANNUITY`).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct application field.
- **Upstream fields:** `AMT_ANNUITY`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect from loan application.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `goods_price` -- numeric
- **Semantic meaning:** Price of goods for consumer loans, where applicable.
- **Possible source:** loan application (`AMT_GOODS_PRICE`).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** direct application field.
- **Upstream fields:** `AMT_GOODS_PRICE`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect from loan application
  (not applicable to non-consumer loans -- a documented fallback rule
  would be needed in a future system, never a silent zero).
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `current_dti` -- numeric
- **Semantic meaning:** Debt-to-income using the current EMI.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `current_dti = AMT_ANNUITY / AMT_INCOME_TOTAL`
  (`NaN` when income is not positive).
- **Upstream fields:** `current_loan_annuity`, `monthly_income`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only when both upstream
  fields are present and income is positive.
- **Foundation vs synthetic:** Home Credit foundation (derived in
  `01_build_home_credit_base.py`).
- **Categorical mapping:** N/A.

### `bureau_dti` -- numeric
- **Semantic meaning:** Bureau-reported debt relative to income.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `bureau_dti = bureau_debt_amount / AMT_INCOME_TOTAL`
  (`NaN` when income is not positive).
- **Upstream fields:** `bureau_debt_amount`, `monthly_income`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only when both upstream
  fields are present.
- **Foundation vs synthetic:** Home Credit foundation (derived in
  `01_build_home_credit_base.py`).
- **Categorical mapping:** N/A.

### `previous_approval_ratio` -- numeric
- **Semantic meaning:** Share of previous applications approved.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `previous_approved_count / previous_application_count`
  (`NaN` when the count is zero).
- **Upstream fields:** `previous_approved_count`,
  `previous_application_count`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only when the applicant
  has previous applications.
- **Foundation vs synthetic:** Home Credit foundation (derived in
  `01_build_home_credit_base.py`).
- **Categorical mapping:** N/A.

### `bureau_overdue_ratio` -- numeric
- **Semantic meaning:** Share of bureau credit currently overdue.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `bureau_overdue_amount / bureau_credit_amount`
  (`NaN` when bureau credit is zero).
- **Upstream fields:** `bureau_overdue_amount`, `bureau_credit_amount`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only when bureau credit
  is positive.
- **Foundation vs synthetic:** Home Credit foundation (derived in
  `01_build_home_credit_base.py`).
- **Categorical mapping:** N/A.

## Group G3 -- Bureau aggregates (foundation, 10)

All ten are per-customer sums over `bureau.csv` tradelines grouped by
`SK_ID_CURR` (`01_build_home_credit_base.py`, `aggregate_bureau`).
Possible source for every field in this group: **credit report**.
None is directly a document field; all require aggregation engineering.
All are mandatory; if bureau history is unavailable the record cannot be
scored in the current contract (a future system needs a documented
no-history rule, never a silent zero).

### `bureau_account_count` -- numeric
- **Semantic meaning:** Number of bureau tradelines.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(1)` over the customer's bureau rows.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `active_credit_count` -- numeric
- **Semantic meaning:** Tradelines with `CREDIT_ACTIVE == "Active"`.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(CREDIT_ACTIVE == "Active")`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `closed_credit_count` -- numeric
- **Semantic meaning:** Tradelines with `CREDIT_ACTIVE == "Closed"`.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(CREDIT_ACTIVE == "Closed")`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `bureau_credit_amount` -- numeric
- **Semantic meaning:** Total bureau credit (`AMT_CREDIT_SUM`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_CREDIT_SUM)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `bureau_debt_amount` -- numeric
- **Semantic meaning:** Current bureau debt (`AMT_CREDIT_SUM_DEBT`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_CREDIT_SUM_DEBT)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `bureau_credit_limit` -- numeric
- **Semantic meaning:** Total bureau credit limit
  (`AMT_CREDIT_SUM_LIMIT`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_CREDIT_SUM_LIMIT)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `bureau_overdue_amount` -- numeric
- **Semantic meaning:** Total bureau overdue (`AMT_CREDIT_SUM_OVERDUE`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_CREDIT_SUM_OVERDUE)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `bureau_overdue_days` -- numeric
- **Semantic meaning:** Summed days past due (`CREDIT_DAY_OVERDUE`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(CREDIT_DAY_OVERDUE)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `bureau_overdue_account_count` -- numeric
- **Semantic meaning:** Tradelines with days past due above zero.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(CREDIT_DAY_OVERDUE > 0)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `credit_prolongation_count` -- numeric
- **Semantic meaning:** Times bureau credits were prolonged
  (`CNT_CREDIT_PROLONG`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(CNT_CREDIT_PROLONG)`.
- **Upstream fields:** bureau tradeline records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

## Group G4 -- Installment aggregates (foundation, 10)

Per-customer aggregates over `installments_payments.csv`
(`aggregate_installments`). Per-installment delay is defined as
`PAYMENT_DELAY = DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT` (positive means
late); `LATE_PAYMENT = (PAYMENT_DELAY > 0)`; `ON_TIME_PAYMENT =
(PAYMENT_DELAY <= 0)`; `PAYMENT_DIFFERENCE = AMT_PAYMENT -
AMT_INSTALMENT`. Possible source for every field: **credit report /
repayment history**. None is a direct document field; all require
aggregation engineering. All mandatory; missing history rejects the
record under the current contract.

### `total_installments` -- numeric
- **Semantic meaning:** Count of scheduled installments.
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `count(AMT_INSTALMENT)`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_amount_due` -- numeric
- **Semantic meaning:** Sum of scheduled installment amounts.
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_INSTALMENT)`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_amount_paid` -- numeric
- **Semantic meaning:** Sum of actual payments.
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_PAYMENT)`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_late_payments` -- numeric
- **Semantic meaning:** Count of late installments.
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(PAYMENT_DELAY > 0)`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_on_time_payments` -- numeric
- **Semantic meaning:** Count of on-time installments.
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(PAYMENT_DELAY <= 0)`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `average_payment_delay` -- numeric
- **Semantic meaning:** Mean days late among late payments (days).
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** mean of positive `PAYMENT_DELAY`, else 0.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_payment_delay_days` -- numeric
- **Semantic meaning:** Total late days across installments.
- **Possible source:** credit report (repayment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum` of positive `PAYMENT_DELAY`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `payment_difference` -- numeric
- **Semantic meaning:** Total paid minus total scheduled.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_PAYMENT - AMT_INSTALMENT)`.
- **Upstream fields:** installment records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `on_time_payment_ratio` -- numeric
- **Semantic meaning:** Share of installments paid on time.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `total_on_time_payments / total_installments`
  (`NaN` when zero installments).
- **Upstream fields:** `total_on_time_payments`, `total_installments`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only with installments
  present.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `payment_coverage_ratio` -- numeric
- **Semantic meaning:** Share of scheduled amount actually paid.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `total_amount_paid / total_amount_due`
  (`NaN` when nothing due).
- **Upstream fields:** `total_amount_paid`, `total_amount_due`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only with amounts due.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

## Group G5 -- Previous applications (foundation, 7)

Per-customer aggregates over `previous_application.csv`
(`aggregate_previous`; `APPROVED = (NAME_CONTRACT_STATUS ==
"Approved")`, `REFUSED = (... == "Refused")`). Possible source:
**credit report**. Aggregation engineering required. All mandatory.

### `previous_application_count` -- numeric
- **Semantic meaning:** Number of previous applications.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** count of previous-application rows.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `previous_approved_count` -- numeric
- **Semantic meaning:** Previous applications approved.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(NAME_CONTRACT_STATUS == "Approved")`.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `previous_refused_count` -- numeric
- **Semantic meaning:** Previous applications refused.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(NAME_CONTRACT_STATUS == "Refused")`.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `previous_credit_amount` -- numeric
- **Semantic meaning:** Total previous credit requested.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_CREDIT)`.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `previous_avg_credit` -- numeric
- **Semantic meaning:** Mean previous credit requested.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_CREDIT)`.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `previous_avg_annuity` -- numeric
- **Semantic meaning:** Mean previous annuity.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_ANNUITY)`.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `previous_avg_down_payment` -- numeric
- **Semantic meaning:** Mean previous down payment.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_DOWN_PAYMENT)`.
- **Upstream fields:** previous-application records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

## Group G6 -- Credit card history (foundation, 9)

Per-customer aggregates over `credit_card_balance.csv`
(`aggregate_card`; includes `BALANCE_LIMIT_RATIO = AMT_BALANCE /
AMT_CREDIT_LIMIT_ACTUAL` with zero limits treated as missing).
Possible source: **credit report**. Aggregation engineering required.
All mandatory.

### `avg_credit_card_balance` -- numeric
- **Semantic meaning:** Mean card balance (`AMT_BALANCE`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_BALANCE)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `max_credit_card_balance` -- numeric
- **Semantic meaning:** Maximum card balance observed.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `max(AMT_BALANCE)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `avg_credit_limit` -- numeric
- **Semantic meaning:** Mean actual credit limit
  (`AMT_CREDIT_LIMIT_ACTUAL`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_CREDIT_LIMIT_ACTUAL)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_card_drawings` -- numeric
- **Semantic meaning:** Total drawings (`AMT_DRAWINGS_CURRENT`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_DRAWINGS_CURRENT)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `total_card_payments` -- numeric
- **Semantic meaning:** Total card payments
  (`AMT_PAYMENT_TOTAL_CURRENT`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `sum(AMT_PAYMENT_TOTAL_CURRENT)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `avg_minimum_payment` -- numeric
- **Semantic meaning:** Mean minimum instalment
  (`AMT_INST_MIN_REGULARITY`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_INST_MIN_REGULARITY)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `avg_credit_utilisation` -- numeric
- **Semantic meaning:** Mean balance-to-limit ratio.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `mean(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL)`
  (zero limits treated as missing).
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `max_card_dpd` -- numeric
- **Semantic meaning:** Maximum days past due on cards (`SK_DPD`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `max(SK_DPD)`.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `max_card_dpd_default` -- numeric
- **Semantic meaning:** Worst card delinquency-default flag (`SK_DPD_DEF`).
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes (aggregation of the DPD-default
  indicator; exact threshold handling per the aggregation code).
- **Derivation:** worst observed `SK_DPD_DEF` value.
- **Upstream fields:** credit-card monthly records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

## Group G7 -- POS cash history (foundation, 6)

Per-customer aggregates over `POS_CASH_balance.csv`. Possible source:
**credit report**. Aggregation engineering required. All mandatory.

### `pos_account_records` -- numeric
- **Semantic meaning:** Number of POS cash records.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** count of POS records.
- **Upstream fields:** POS cash records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `avg_pos_installments` -- numeric
- **Semantic meaning:** Mean POS instalment count.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** mean of POS instalment counts.
- **Upstream fields:** POS cash records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `avg_future_installments` -- numeric
- **Semantic meaning:** Mean remaining POS instalments.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** mean of remaining instalment counts.
- **Upstream fields:** POS cash records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `pos_dpd_count` -- numeric
- **Semantic meaning:** Count of POS DPD occurrences.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** count of POS delinquency records.
- **Upstream fields:** POS cash records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `max_pos_dpd` -- numeric
- **Semantic meaning:** Maximum POS days past due.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** max POS DPD.
- **Upstream fields:** POS cash records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

### `max_pos_dpd_default` -- numeric
- **Semantic meaning:** Worst POS delinquency-default flag.
- **Possible source:** credit report.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes (aggregation of the
  DPD-default indicator; exact threshold handling per the
  aggregation code).
- **Derivation:** worst observed POS DPD-default value.
- **Upstream fields:** POS cash records.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Home Credit foundation.
- **Categorical mapping:** N/A.

## Group G8 -- Indian context (synthetic, 3)

### `city_tier` -- categorical
- **Semantic meaning:** Census-based city tier of residence.
- **Possible source:** user profile/input (city of residence mapped to
  the Census tier table in `config/indian_parameters.json`).
- **Directly extractable:** Yes, via tier lookup.
- **Requires feature engineering:** Yes, city-to-tier mapping.
- **Derivation:** map residence city to `Tier_1`/`Tier_2`/`Tier_3`.
- **Upstream fields:** city of residence.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect city of residence.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** Yes. Observed levels: `Tier_1`, `Tier_2`,
  `Tier_3`.

### `occupation_band` -- categorical
- **Semantic meaning:** PLFS-based occupation band.
- **Possible source:** user profile/input (occupation mapped to the
  PLFS band table).
- **Directly extractable:** Yes, via band lookup.
- **Requires feature engineering:** Yes, occupation-to-band mapping.
- **Derivation:** map occupation to `Salaried`/`Self_Employed`/
  `Casual_Worker`/`Other`.
- **Upstream fields:** occupation.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect occupation.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** Yes. Observed test levels: `Other`,
  `Salaried` (further bands exist in the reference table).

### `indian_household_size` -- numeric
- **Semantic meaning:** Household size with local variation.
- **Possible source:** user profile/input (family size adjusted).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `clip(family_size + household_variation, 1, 10)`
  as integer (research code).
- **Upstream fields:** `family_size`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; collect family size.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

## Group G9 -- Expenses (synthetic, 9)

The seven category expenses are research-generated with MoSPI HCES
2023-24 urban reference shares (`config/indian_parameters.json`) and
lognormal shocks. In a future system the honest source is **bank
statement transaction categorization** (or user-estimated budgets with a
documented estimation rule -- never silent defaults).

### `food_expense` -- numeric
- **Semantic meaning:** Monthly food expenditure (HCES food share
  reference 0.4031).
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes, transaction categorization
  and summation.
- **Derivation:** sum of food-category transactions (research:
  share-based generation with shocks).
- **Upstream fields:** categorized food transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `rent_expense` -- numeric
- **Semantic meaning:** Monthly rent expenditure (HCES rent share
  reference 0.0650).
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** sum of rent-category transactions.
- **Upstream fields:** categorized rent transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `education_expense` -- numeric
- **Semantic meaning:** Monthly education expenditure, zero when the
  applicant has no children (HCES education share reference 0.0590).
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** sum of education-category transactions; zero when
  `children_count` is zero.
- **Upstream fields:** categorized education transactions,
  `children_count`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `healthcare_expense` -- numeric
- **Semantic meaning:** Monthly healthcare expenditure (HCES medical
  shares reference 0.0194 hospitalization + 0.0385
  non-hospitalization).
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** sum of healthcare-category transactions.
- **Upstream fields:** categorized healthcare transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `transport_expense` -- numeric
- **Semantic meaning:** Monthly transport expenditure (HCES conveyance
  share reference 0.0836).
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** sum of transport-category transactions.
- **Upstream fields:** categorized transport transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `utility_expense` -- numeric
- **Semantic meaning:** Monthly utility expenditure (HCES fuel/light
  share reference 0.0553).
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** sum of utility-category transactions.
- **Upstream fields:** categorized utility transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `discretionary_expense` -- numeric
- **Semantic meaning:** Monthly discretionary expenditure.
- **Possible source:** bank statement (transaction categorization).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** sum of discretionary-category transactions.
- **Upstream fields:** categorized discretionary transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `synthetic_total_expense` -- numeric
- **Semantic meaning:** Total monthly expenditure.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `food + rent + education + healthcare + transport +
  utility + discretionary` (all seven categories above).
- **Upstream fields:** the seven expense categories.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only when all seven
  categories are present.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `synthetic_spending_ratio` -- numeric
- **Semantic meaning:** Expenditure share of income, clipped to
  [0.40, 0.88] in research.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `synthetic_total_expense / income` (research clips
  to [0.40, 0.88]).
- **Upstream fields:** `synthetic_total_expense`, `monthly_income`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only with positive income.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

## Group G10 -- EMI, surplus, savings and deposits (synthetic, 7)

### `synthetic_total_emi` -- numeric
- **Semantic meaning:** Total monthly EMI outflow.
- **Possible source:** derived from other features (loan schedule /
  credit report in a future system).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `min(current_loan_annuity, 0.50 * monthly_income)`
  (research cap).
- **Upstream fields:** `current_loan_annuity`, `monthly_income`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only with both upstream
  fields present.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `available_surplus` -- numeric
- **Semantic meaning:** Income left after expenses and EMI, floored
  at zero.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `max(monthly_income - synthetic_total_expense -
  synthetic_total_emi, 0)`.
- **Upstream fields:** `monthly_income`, `synthetic_total_expense`,
  `synthetic_total_emi`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only when all upstream
  fields are present.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `monthly_savings` -- numeric
- **Semantic meaning:** Monthly amount actually saved (capped by
  surplus; research models a behaviour-dependent portion of surplus).
- **Possible source:** bank statement (savings transactions / balance
  progression).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** research: `min(surplus * saving_rate_from_surplus *
  shock, surplus)`; future: measured inflow-minus-outflow retained
  savings from statements.
- **Upstream fields:** `available_surplus` (research); statement
  transactions (future).
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `savings_rate` -- numeric
- **Semantic meaning:** Monthly savings as a share of income, clipped
  to [0, 0.80].
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `clip(monthly_savings / monthly_income, 0, 0.80)`
  (0 when income is not positive).
- **Upstream fields:** `monthly_savings`, `monthly_income`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only with positive income.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `savings_balance` -- numeric
- **Semantic meaning:** Accumulated savings balance.
- **Possible source:** bank statement (account balance).
- **Directly extractable:** Yes, from a balance record.
- **Requires feature engineering:** No (research accumulates it from
  savings history; a real system reads the balance).
- **Derivation:** measured balance (research: `monthly_savings *
  history_months * retention factor`).
- **Upstream fields:** account balance record.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `fd_amount` -- numeric
- **Semantic meaning:** Fixed deposit amount (capped by savings
  balance in research).
- **Possible source:** investment document (FD advice/statement).
- **Directly extractable:** Yes, from the FD document.
- **Requires feature engineering:** No.
- **Derivation:** stated FD amount.
- **Upstream fields:** FD document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; a documented no-holding rule
  would be needed in a future system, never a silent zero.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `rd_contribution` -- numeric
- **Semantic meaning:** Monthly recurring-deposit contribution (capped
  by monthly savings in research).
- **Possible source:** investment document (RD statement).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated RD contribution.
- **Upstream fields:** RD document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding rule caveat as
  `fd_amount`.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

## Group G11 -- Digital payments (synthetic, 3)

### `upi_spending` -- numeric
- **Semantic meaning:** Monthly UPI spend, capped by total expenses.
- **Possible source:** bank statement (UPI transaction aggregation;
  NPCI UPI context in research).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes, UPI transaction aggregation
  with the `min(spend, total_expense)` cap.
- **Derivation:** `min(expense * digital_share, total_expense)`.
- **Upstream fields:** UPI transactions, `synthetic_total_expense`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `upi_transaction_count` -- numeric
- **Semantic meaning:** Monthly UPI transaction count (at least 1 in
  research when spending exists).
- **Possible source:** bank statement (UPI transaction count).
- **Directly extractable:** Yes, by counting UPI transactions.
- **Requires feature engineering:** Yes, counting only.
- **Derivation:** count of UPI transactions (research:
  `max(round(spend / ticket_size), 1)`).
- **Upstream fields:** UPI transactions.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `digital_payment_ratio` -- numeric
- **Semantic meaning:** UPI share of total expenses.
- **Possible source:** derived from other features.
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** `upi_spending / synthetic_total_expense`
  (0 when expenses are zero).
- **Upstream fields:** `upi_spending`, `synthetic_total_expense`.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; derive only with expenses present.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

## Group G12 -- Investments and insurance (synthetic, 8)

Contributions are capped by monthly savings in research; holdings and
premiums are conditional on participation. Future source for every field
in this group: the corresponding **investment/insurance document**.
None is directly a model input without the document; none may be
defaulted silently.

### `sip_contribution` -- numeric
- **Semantic meaning:** Monthly systematic investment plan amount
  (AMFI SIP context in research).
- **Possible source:** investment document (SIP statement).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated SIP amount.
- **Upstream fields:** SIP document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; documented no-holding rule
  needed in future, never silent zero.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `mutual_fund_balance` -- numeric
- **Semantic meaning:** Mutual fund holdings balance.
- **Possible source:** investment document (mutual fund statement).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated holdings balance.
- **Upstream fields:** mutual fund document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding caveat.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `ppf_contribution` -- numeric
- **Semantic meaning:** Public provident fund contribution.
- **Possible source:** investment document (PPF statement).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated PPF amount.
- **Upstream fields:** PPF document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding caveat.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `nps_contribution` -- numeric
- **Semantic meaning:** National pension system contribution.
- **Possible source:** investment document (NPS statement).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated NPS amount.
- **Upstream fields:** NPS document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding caveat.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `health_insurance` -- numeric
- **Semantic meaning:** Health insurance holding flag/amount (0/1 in
  test data).
- **Possible source:** insurance document (health policy).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated holding.
- **Upstream fields:** health insurance document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding caveat.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `life_insurance` -- numeric
- **Semantic meaning:** Life insurance holding flag/amount (0/1 in
  test data).
- **Possible source:** insurance document (life policy).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated holding.
- **Upstream fields:** life insurance document.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding caveat.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `insurance_premium` -- numeric
- **Semantic meaning:** Periodic insurance premium outflow.
- **Possible source:** insurance document (premium schedule).
- **Directly extractable:** Yes.
- **Requires feature engineering:** No.
- **Derivation:** stated premium.
- **Upstream fields:** insurance documents.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; same no-holding caveat.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `insurance_payment_consistency` -- numeric
- **Semantic meaning:** Share of the last 12 premium periods paid
  (0 when no policy is held).
- **Possible source:** insurance document (premium payment history).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes, payment-history ratio.
- **Derivation:** paid periods / 12 over the trailing year
  (research: binomial draws; 0 with no policy).
- **Upstream fields:** premium payment history.
- **Mandatory:** Yes.
- **If unavailable:** record rejected.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

## Group G13 -- Cash-flow history (synthetic, 4)

Twelve-month monthly cash flow is defined as income minus expenses
minus commitments (EMI plus insurance premium); the four features are
its mean, standard deviation, minimum, and count of negative months.
Future source: **bank statement** monthly net-flow series. All four
require series engineering. All mandatory.

### `cash_flow_mean` -- numeric
- **Semantic meaning:** Mean monthly net cash flow.
- **Possible source:** bank statement (monthly net flows).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** mean over 12 months of
  `income - expenses - (EMI + insurance premium)`.
- **Upstream fields:** monthly income, expenses, EMI, premium series.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; requires a 12-month series.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `cash_flow_std` -- numeric
- **Semantic meaning:** Standard deviation of monthly net cash flow.
- **Possible source:** bank statement (monthly net flows).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** standard deviation over the same 12-month series.
- **Upstream fields:** monthly income, expenses, EMI, premium series.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; requires a 12-month series.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `cash_flow_min` -- numeric
- **Semantic meaning:** Worst monthly net cash flow.
- **Possible source:** bank statement (monthly net flows).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** minimum over the same 12-month series.
- **Upstream fields:** monthly income, expenses, EMI, premium series.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; requires a 12-month series.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

### `cash_flow_negative_months` -- numeric
- **Semantic meaning:** Count of months with negative net cash flow.
- **Possible source:** bank statement (monthly net flows).
- **Directly extractable:** No.
- **Requires feature engineering:** Yes.
- **Derivation:** count of months with net flow below zero.
- **Upstream fields:** monthly income, expenses, EMI, premium series.
- **Mandatory:** Yes.
- **If unavailable:** record rejected; requires a 12-month series.
- **Foundation vs synthetic:** Indian synthetic layer.
- **Categorical mapping:** N/A.

## Verification summary

- 98 features documented: 86 numeric, 12 categorical.
- 64 Home Credit foundation features (verified present in
  `output/home_credit_base.csv`, including 10 categoricals).
- 34 Indian synthetic-layer features (exact match with the
  `indian_columns` list, including `city_tier` and `occupation_band`).
- Categorical levels quoted from observed test-data values; the
  encoder ignores unseen levels at inference.
- No real-world availability invented: every future source above is
  either the research script section that generated the field or the
  document class that would honestly supply it.
