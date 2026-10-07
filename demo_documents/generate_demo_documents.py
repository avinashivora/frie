"""Generate the clearly synthetic FRIE demo documents (no real personal data).

Outputs (all prefixed, all invented for pipeline demonstration only):
  01_salary_slip.pdf        text salary slip (embedded-text extraction path)
  02_bank_statement.pdf      12 months of categorized transactions
  03_credit_report.pdf       structured tradeline/installment/card/POS records
  04_insurance_policy.pdf    premium plus 12 monthly payment dates
  05_investment_statement.pdf all six product holdings
  06_scanned_salary_slip.png scanned-style salary slip (Tesseract OCR path)
  06_scanned_salary_slip.pdf image-only PDF of the same scan (OCR fallback path)
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent


def write_pdf(name: str, lines: list[str], width: int = 1200, fontsize: int = 10) -> Path:
    document = pymupdf.open()
    try:
        page = document.new_page(width=width, height=1400)
        page.insert_text((72, 72), "\n".join(lines), fontsize=fontsize)
        path = HERE / name
        document.save(path)
        return path
    finally:
        document.close()


def write_png(name: str, lines: list[str]) -> Path:
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        font = ImageFont.load_default(size=30)
    image = Image.new("RGB", (1000, 120 + 55 * len(lines)), color="white")
    draw = ImageDraw.Draw(image)
    top = 30
    for line in lines:
        draw.text((30, top), line, fill="black", font=font)
        top += 55
    path = HERE / name
    image.save(path, format="PNG")
    return path


def salary_lines() -> list[str]:
    return [
        "FAKE DEMO SALARY SLIP - SYNTHETIC DATA ONLY",
        "Employee Name: Demo User",
        "Employer: Demo Enterprises",
        "Salary Period: June 2024",
        "Basic: Rs. 60000.00",
        "Gross: Rs. 95000.00",
        "Net Salary: Rs. 78000.00",
        "Pay Date: 30/06/2024",
    ]


def bank_lines() -> list[str]:
    lines = ["FAKE DEMO BANK STATEMENT - SYNTHETIC DATA ONLY", "Account No: 987654321098"]
    balance = 120000.0
    for month in range(1, 13):
        tag = f"{month:02d}/2024"
        for day, description, debit, credit in (
            ("05", "SALARY-CREDIT", 0.0, 95000.0),
            ("08", "UPI-BIGBASKET-GROCERY", 3000.0, 0.0),
            ("11", "UPI-SWIGGY-FOOD", 2500.0, 0.0),
            ("14", "ELECTRICITY-BILL-NEFT", 1500.0, 0.0),
            ("15", "HOUSE-RENT-NEFT", 18000.0, 0.0),
            ("18", "OLA-CAB-RIDE", 1200.0, 0.0),
            ("22", "SIP-HDFC-MUTUALFUND", 5000.0, 0.0),
        ):
            balance += credit - debit
            lines.append(f"{day}/{tag} {description} {debit:,.2f} {credit:,.2f} {balance:,.2f}")
    return lines


def credit_lines() -> list[str]:
    lines = [
        "FAKE DEMO CREDIT REPORT - SYNTHETIC DATA ONLY",
        "TRADELINE | lender=Demo Bank | type=Credit Card | limit=500000 | balance=125000 "
        "| debt=125000 | overdue=0 | dpd=0 | status=Active",
        "TRADELINE | lender=Demo Housing | type=Home Loan | limit=2000000 | balance=1500000 "
        "| debt=1500000 | overdue=5000 | dpd=15 | prolong=1 | status=Active",
    ]
    for month in range(1, 13):
        lines.append(
            f"INSTALLMENT | date=05/{month:02d}/2024 | paid_date=05/{month:02d}/2024 "
            f"| due=18000.00 | paid=18000.00"
        )
    lines += [
        "PREVAPP | status=Approved | credit=300000 | annuity=15000 | down=20000 | goods=280000",
        "PREVAPP | status=Refused | credit=100000 | annuity=8000 | down=10000 | goods=90000",
        "CARDMONTH | balance=125000 | limit=500000 | drawings=20000 | payments=18000 "
        "| minimum=5000 | dpd=0 | dpd_default=0",
        "CARDMONTH | balance=130000 | limit=500000 | drawings=25000 | payments=20000 "
        "| minimum=5200 | dpd=5 | dpd_default=0",
        "POSREC | installments=12 | future=6 | dpd=0 | dpd_default=0",
        "POSREC | installments=6 | future=2 | dpd=10 | dpd_default=1",
    ]
    return lines


def main() -> None:
    made = []
    made.append(write_pdf("01_salary_slip.pdf", salary_lines()))
    made.append(write_pdf("02_bank_statement.pdf", bank_lines()))
    made.append(write_pdf("03_credit_report.pdf", credit_lines()))
    made.append(write_pdf("07_loan_document.pdf", [
        "FAKE DEMO LOAN DOCUMENT - SYNTHETIC DATA ONLY",
        "Loan Amount: Rs. 990000.00",
        "EMI: Rs. 28944.00",
        "Cash loan facility",
        "Dated: 15/01/2024",
    ]))
    made.append(write_pdf("04_insurance_policy.pdf", [
        "FAKE DEMO INSURANCE POLICY - SYNTHETIC DATA ONLY",
        "Life Insurance Policy",
        "Premium: Rs. 1200.00",
        "Frequency: Monthly",
        "Status: In-force",
    ] + [f"Premium paid on 05/{month:02d}/2024" for month in range(1, 13)]))
    made.append(write_pdf("05_investment_statement.pdf", [
        "FAKE DEMO INVESTMENT STATEMENT - SYNTHETIC DATA ONLY",
        "Fixed Deposit: Rs. 200000.00",
        "Recurring Deposit: Rs. 50000.00",
        "SIP: Rs. 5000.00",
        "Mutual Fund: Rs. 150000.00",
        "PPF: Rs. 200000.00",
        "NPS: Rs. 100000.00",
    ]))
    scan_lines = [
        "FAKE DEMO SCAN - SYNTHETIC DATA ONLY",
        "Employee Name: Demo User",
        "Gross: Rs. 95000.00",
        "Net Salary: Rs. 78000.00",
    ]
    made.append(write_png("06_scanned_salary_slip.png", scan_lines))

    scan_pdf = pymupdf.open()
    try:
        page = scan_pdf.new_page(width=1000, height=120 + 55 * len(scan_lines))
        page.insert_image(page.rect, stream=open(HERE / "06_scanned_salary_slip.png", "rb").read())
        scan_path = HERE / "06_scanned_salary_slip.pdf"
        scan_pdf.save(scan_path)
        made.append(scan_path)
    finally:
        scan_pdf.close()
    for path in made:
        print(f"wrote {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
