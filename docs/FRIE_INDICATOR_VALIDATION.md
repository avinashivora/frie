# FRIE indicator verification — 2026-10-03

Original methodology: `C:\Users\danly\Downloads\FRIE_Score_Generation_Methodology_v1.docx`.
Original implementation: `C:\Users\danly\Downloads\Frie_score.ipynb`.
Reference output: `D:\frie\Model Train\frie_scored_1000_calibrated.csv` (1,000 rows).

| Indicator | Max absolute difference | Mean absolute difference |
|---|---:|---:|
| income_stability | 1.42108547152e-14 | 3.97903932026e-16 |
| cashflow_stability | 1.42108547152e-14 | 1.80300219199e-15 |
| payment_discipline | 2.84217094304e-14 | 1.96820337806e-15 |
| savings_discipline | 1.42108547152e-14 | 8.90176821144e-16 |
| commitment_adherence | 1.42108547152e-14 | 7.03437308402e-16 |
| debt_burden | 1.42108547152e-14 | 4.90718576884e-16 |
| financial_stress | 2.13162820728e-14 | 2.09121608918e-15 |
| financial_resilience | 1.42108547152e-14 | 1.12894416038e-15 |

The backend preserves floating-point precision; display rounding occurs in the UI. Notebook compatibility mode is used solely for reference validation. In normal assessments all-missing indicators are limited/unavailable rather than invented neutral values, except the documented Income Stability neutral 50. Unknown investments are not converted to zero. Indicators use source values, never model-imputed values or SHAP contributions.

The V2 model remains unchanged and separately generates the assessment score.
