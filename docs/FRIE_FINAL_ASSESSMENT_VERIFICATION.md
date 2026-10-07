# FRIE final assessment verification - 2026-10-03

1. Original implementation: `C:\Users\danly\Downloads\Frie_score.ipynb`.
2. Indicator service: `backend/app/services/indicator_service.py`, all eight indicators.
3. Authority: the original notebook plus `C:\Users\danly\Downloads\FRIE_Score_Generation_Methodology_v1.docx`. No retraining, model replacement, or new indicator formulas.
4. Original/new validation: all 1,000 reference rows compared. Maximum absolute difference across indicators: 2.84217094304e-14. Per-indicator maximum and mean differences are in FRIE_INDICATOR_VALIDATION.md. Normal application missing-data states are intentionally explicit; notebook compatibility mode is used for reference comparison.
5. Full routing: authenticated `/analysis/assess` invokes the strict V2 prediction service shared with `/predict` whenever the internal contract is READY. Route regression tests forbid calling available-data prediction in this branch.
6. Estimated routing: the same authenticated route invokes the existing V2 service shared with `/predict/partial`, using its saved preprocessing. No separate model and no feature-count threshold. Tests forbid strict full prediction in this branch. The raw research endpoint remains internal; normal UI only exposes Estimated FRIE Score.
7. Confirmed no loan/insurance/investments: saved and refreshed in the browser; sources complete; scoring remains eligible. Recalculated estimated score 71.7.
8. Unknown: remains unknown, never converted into zero. Source guidance and limited indicators reflect unavailable evidence. An empty or failed reviewed extraction is not sufficient financial evidence.
9. Indicator UI: all eight actual dimensions, progress bars, readable Details, limited information states, and the 12.5% framework note. Dashboard, Analysis and Report use backend values.
10. Recommendations: one backend service; indicator threshold below 55; priorities High below 35, Medium below 45, Low below 55. Missing-source guidance is informational. No financial-product or exact score-uplift claims.
11. Recommendation UI: Dashboard top three and full Recommendations page share persisted results; actual priority counts, verified full user has two Medium recommendations (Debt Burden and Income Stability).
12. SHAP: genuine TreeSHAP remains separate from methodology indicators. Readable factors visibly verified; no raw names, preprocessing terminology or causal claims.
13. Persistence: refresh retained score 78.3, complete state, all indicators, recommendations and history; estimated history retains explicit estimated labels. Exact stored full score is 78.32.
14. Invalidation: editing the synthetic income (using the salary document's existing net amount) hid the stale assessment. Recalculation restored current results. Deleting investment upload changed source to Required and hid the full score; uploading the same document, extracting, accepting and recalculating restored READY and 78.3.
15. Backend tests: complete suite 128 passed in 559.81 seconds, including prediction and real PNG/scanned-PDF OCR. Subsequent targeted tests after final source checks: 23 passed. After strict floating-point parity checks: 10 passed. No tests removed.
16. Frontend build: npm run build passed after final frontend edits (2,228 modules). Nonblocking bundle-size warning remains.
17. Fresh browser journey: registered frie.final.demo.20261003@example.com, logged out and logged in. Empty Dashboard showed no score, human-readable required sources, no feature count/partial UI. Profile validation visible, then save succeeded. Completed Profile without financial data remained insufficient.
18. Bank-backed browser journey: existing synthetic CSV uploaded, parsed all 84 transactions, reviewed and accepted. Profile + income + bank with additional sources unknown generated Estimated FRIE Score 60.9 (Good), with genuine limited indicator states and missing-source recommendations. Existing raidq synthetic session also verified a saved estimated assessment with readable explanation.
19. Complete browser journey: uploaded, extracted and accepted salary, bank PDF, credit, insurance, investment and loan documents. Internal READY 98/98. Browser full score 78.3 Excellent matches stored backend 78.32. All eight indicators populated. Normal full-ready flow contains no estimated/partial wording. Source and screen text leak checks passed.
20. Edit/delete browser journey: profile edit, stale display, recalculation, investment document delete, source-level guidance, document restoration, re-extraction/review and recalculation all visibly verified. Only synthetic demo data used.
21. Remaining limitations: no functional blocker in verified journeys. Estimated assessments intentionally have limited indicators; SHAP is explanatory, not causal. Build chunk-size and two dependency warnings remain. Automatic approval review blocked cleanup of generated test temp folders with 'blocked by policy'; folders retained. No commit or push.

## Bank verification

The CSV is the existing deterministic equivalent of the same demo PDF (84 transactions, 12 months, credits 1,140,000 and debits 374,400). CSV parsing, classification, monthly aggregation and engineered FRIE values were exercised through the browser and backend tests. Structured input now takes precedence over the PDF representation to prevent duplicate counting; fallback PDF extraction and scanned-document OCR remain functional. The summary reports actual months rather than counting derived fields.

## Complete indicator values

| Indicator | Score |
|---|---:|
| Income Stability | 41.700000 |
| Cashflow Stability | 93.431579 |
| Payment Discipline | 100.000000 |
| Savings Discipline | 100.000000 |
| Commitment Adherence | 100.000000 |
| Debt Burden | 35.960421 |
| Financial Stress | 87.559649 |
| Financial Resilience | 91.789474 |

Screenshots: verification/full-report.jpg, verification/full-analysis.jpg, verification/estimated-assessment.jpg, verification/deleted-source-readiness.jpg, verification/recommendations.jpg.
