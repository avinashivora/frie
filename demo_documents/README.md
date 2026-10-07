# FRIE Synthetic Demo Documents

Every file in this directory is **entirely synthetic demonstration data**.
Names, amounts, account numbers, and dates are invented for pipeline
testing only. No real personal financial data is present or implied.

Regenerate at any time with the project virtual environment (from this
directory):

```powershell
..\backend\.venv\Scripts\python.exe generate_demo_documents.py
```

Files (upload each under its matching document type, then extract and
review):

- `01_salary_slip.pdf` -- text salary slip (embedded-text extraction path)
- `02_bank_statement.pdf` -- 12 months of categorized transactions
  (salary credits, rent, UPI grocery, UPI food, electricity, transport,
  investment SIP)
- `03_credit_report.pdf` -- structured tradeline / installment /
  previous-application / card / POS records in the documented demo format
- `04_insurance_policy.pdf` -- premium plus 12 monthly payment dates
- `05_investment_statement.pdf` -- all six product holdings
- `06_scanned_salary_slip.png` -- scanned-style salary slip
  (Tesseract OCR path)
- `06_scanned_salary_slip.pdf` -- image-only PDF of the same scan
  (PDF-to-image OCR fallback path)
- `07_loan_document.pdf` -- loan amount and EMI (current-loan fields)

Demo flow: profile -> declarations -> upload matching documents ->
extract -> review and accept -> rebuild feature data.
