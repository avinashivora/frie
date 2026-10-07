Build a functional web application called FRIE — Financial Reliability Intelligence Engine.

IMPORTANT:
Use the attached/existing FRIE Figma design as the PRIMARY visual reference.

Do NOT redesign the interface from scratch.

Preserve the existing:
- visual design
- layout
- typography
- colors
- cards
- dashboards
- navigation
- spacing
- FRIE branding

The goal is to turn the existing FRIE UI into a functional interactive web application.

==================================================
1. AUTHENTICATION
==================================================

Create a functional demo authentication system.

The application has four user roles:

1. Individual
2. Bank
3. NBFC
4. Insurance Company

Create demo accounts:

Individual:
Email: individual@frie.demo
Password: FRIE123

Bank:
Email: bank@frie.demo
Password: FRIE123

NBFC:
Email: nbfc@frie.demo
Password: FRIE123

Insurance:
Email: insurance@frie.demo
Password: FRIE123

The login page must contain:
- Email field
- Password field
- Show/hide password
- Remember me
- Forgot password
- Sign In button

The Sign In button must validate the demo credentials and route the user to the correct dashboard based on their role.

Do NOT make the entire page clickable.

Only actual buttons, inputs, links, cards, tabs and navigation items should be interactive.

==================================================
2. LANDING PAGE
==================================================

Preserve the existing FRIE landing page.

Make these elements functional:

- Get Your FRIE Score → Login
- Learn More → relevant information section
- Login → Login page
- Navigation links → corresponding sections/pages

Do not create invisible full-page clickable overlays.

==================================================
3. INDIVIDUAL FLOW
==================================================

After Individual login:

Login
→ Individual Dashboard
→ Document Upload
→ Financial Details
→ Financial Analysis
→ FRIE Score / Report
→ Recommendations
→ History

Individual Dashboard should display:
- FRIE Score
- Score category
- Confidence
- Income Stability
- Credit Behaviour
- Savings Discipline
- Payment Discipline
- Debt Burden
- Financial Resilience
- Recent activity
- Recommendations

==================================================
4. DOCUMENT UPLOAD
==================================================

Create a functional document upload interface.

Allow demo uploads for:

- PAN
- Aadhaar / identity document
- Salary Slip
- Bank Statement
- CIBIL / Credit Report
- Insurance Document
- Investment Statement

Show:
- file name
- document type
- upload status
- verification status

For the prototype/MVP, document processing can use mock data.

Do not claim that real OCR or financial APIs are being used.

==================================================
5. FINANCIAL ANALYSIS
==================================================

After documents are uploaded, show a processing/analysis screen.

Use realistic demo financial data.

Calculate/display:

- Monthly Income
- Monthly Expenses
- Monthly Savings
- Existing Debt
- EMI
- Credit Score
- Savings Rate
- Debt-to-Income Ratio
- Payment Discipline
- Income Stability

Then generate a demo FRIE score.

==================================================
6. FRIE SCORE
==================================================

Create a FRIE score between 0 and 100.

Display:

FRIE Score
Reliability Category
Confidence Score

Show component scores:

- Income Stability
- Credit Behaviour
- Savings Discipline
- Payment Discipline
- Debt Burden
- Financial Resilience
- Insurance Protection
- Investment Behaviour

Show a clear explanation of factors that increased or decreased the score.

This is a DEMO scoring implementation only.

Do not claim that this is a production ML model.

==================================================
7. BANK DASHBOARD
==================================================

After Bank login, show the existing Bank dashboard.

Features:

- Customer search
- Customer profile
- FRIE score
- FRIE component breakdown
- Financial reliability report
- Loan decision support
- Customer history

Allow the bank user to select a demo customer and view their FRIE profile.

==================================================
8. NBFC DASHBOARD
==================================================

After NBFC login:

- Customer applications
- Customer profile
- FRIE score
- Financial reliability
- Risk indicators
- Loan decision support
- Recommendations

==================================================
9. INSURANCE DASHBOARD
==================================================

After Insurance login:

- Customer profile
- FRIE score
- Financial stability
- Income stability
- Affordability indicators
- Existing insurance
- Recommendations

==================================================
10. NAVIGATION
==================================================

Make navigation functional.

Include:

- Dashboard
- FRIE Score
- Customers
- Documents
- Financial Analysis
- Reports
- Recommendations
- History
- Profile
- Settings
- Notifications
- Help & Support
- Logout

Logout must return to the Login page.

==================================================
11. DATA
==================================================

Use realistic DEMO/SYNTHETIC customer data.

Do NOT use real personal information.

Create several demo customers with different financial profiles.

Example:

Customer 1:
High income
Low debt
Strong savings
Excellent payment behaviour

Customer 2:
Moderate income
Moderate debt
Average savings

Customer 3:
High debt
Low savings
Irregular payments

==================================================
12. RESPONSIVENESS
==================================================

Make the application usable on desktop screens.

Maintain the existing desktop dashboard design.

==================================================
13. IMPORTANT UI RULE
==================================================

Never make an entire frame/page clickable.

Clickable areas must be limited to the actual UI element:

- buttons
- cards
- navigation links
- tabs
- form controls
- icons where appropriate

Do not place one giant invisible clickable rectangle over a page.

==================================================
14. FUTURE ARCHITECTURE
==================================================

Structure the application so that the demo/mock scoring can later be replaced with:

Frontend
→ Backend API
→ Feature Engineering Pipeline
→ FRIE ML Model
→ Database

For now, use mock/demo data for the backend functionality.

The purpose of this version is to create a functional FRIE MVP/prototype that can later be connected to the actual ML model and financial data pipeline.