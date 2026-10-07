import type { FeatureReadiness, ProfileEnvelope } from "../../services/api";

export type ReadinessSourceKey = "profile" | "income" | "bank" | "credit" | "insurance" | "investments" | "loans";

export interface ReadinessSource {
  key: ReadinessSourceKey;
  title: string;
  uploadTitle: string;
  description: string;
  accepted: string;
}

export const READINESS_SOURCES: ReadinessSource[] = [
  { key: "profile", title: "Profile", uploadTitle: "Complete your profile", description: "Add your basic, household, housing, and employment information.", accepted: "Profile details" },
  { key: "income", title: "Income & Employment", uploadTitle: "Add salary or income details", description: "FRIE uses your income and work history to understand financial stability.", accepted: "Profile details or a salary / income document" },
  { key: "bank", title: "Bank Statement", uploadTitle: "Bank statement required", description: "Upload a recent statement or supported transaction file so FRIE can analyse income, expenses, savings, and cash flow.", accepted: "PDF, image, CSV, Excel, or TXT" },
  { key: "credit", title: "Credit Report", uploadTitle: "Credit report required", description: "Upload your credit report to analyse credit and repayment history.", accepted: "PDF, PNG, or JPEG" },
  { key: "insurance", title: "Insurance Details", uploadTitle: "Add your insurance details", description: "Share policy and payment information, or confirm that you do not hold insurance.", accepted: "Profile declaration or PDF, PNG, or JPEG" },
  { key: "investments", title: "Investment Details", uploadTitle: "Add your investment details", description: "Share your investment information, or confirm which products you do not hold.", accepted: "Profile declarations or PDF, PNG, or JPEG" },
  { key: "loans", title: "Loan Details", uploadTitle: "Add your loan details", description: "Share loan and repayment information, or confirm that you do not have a loan.", accepted: "Profile declaration or PDF, PNG, or JPEG" },
];

const FEATURE_PATTERNS: Record<Exclude<ReadinessSourceKey, "profile">, RegExp[]> = {
  income: [/monthly_income/, /employment_years/, /income_type/, /occupation/, /organization_type/, /contract_type/, /occupation_band/, /available_surplus/],
  bank: [/expense/, /cash_flow/, /cashflow/, /spending/, /savings/, /surplus/, /upi_/, /digital_payment/, /synthetic_total/],
  credit: [
    /bureau_/, /credit_/, /card_/, /installment/, /pos_/, /overdue/, /late_payment/,
    /^(total_(late|on_time|payment_delay|amount_due|amount_paid)|average_payment|payment_(difference|coverage)|on_time_payment)/,
    /^previous_(application|approved|refused|credit|avg_)/,
  ],
  insurance: [/insurance/],
  investments: [/fd_/, /rd_/, /sip_/, /mutual_fund/, /ppf_/, /nps_/, /investment/],
  loans: [/loan_/, /annuity/, /emi/, /goods_price/, /current_dti/, /debt/],
};

export function sourceKeyForFeature(feature: string): ReadinessSourceKey[] {
  const key = feature.toLowerCase();
  const sources: ReadinessSourceKey[] = [];
  if (/(^|_)(gender|age|children_count|family_size|family_status|education_level|housing_type|owns_car|owns_property|city_tier|organization_type|income_type|contract_type|occupation)(_|$)/.test(key)) sources.push("profile");
  for (const [source, patterns] of Object.entries(FEATURE_PATTERNS) as [Exclude<ReadinessSourceKey, "profile">, RegExp[]][]) {
    if (patterns.some(pattern => pattern.test(key))) sources.push(source);
  }
  return sources.length ? sources : ["profile"];
}

export function sourceCompletion(readiness: FeatureReadiness | null, profile: ProfileEnvelope | null): Record<ReadinessSourceKey, boolean> {
  const missingBySource = new Set<ReadinessSourceKey>();
  for (const item of readiness?.missing ?? []) {
    for (const source of sourceKeyForFeature(item.feature)) missingBySource.add(source);
  }
  return {
    profile: profile?.readiness.profile_ready ?? false,
    income: !missingBySource.has("income"),
    bank: !missingBySource.has("bank"),
    credit: !missingBySource.has("credit"),
    insurance: !missingBySource.has("insurance"),
    investments: !missingBySource.has("investments"),
    loans: !missingBySource.has("loans"),
  };
}

export function profileMissingCategories(missingFields: { feature: string }[]): string[] {
  const categories = new Set<string>();
  for (const item of missingFields) {
    const field = item.feature.toLowerCase();
    if (/gender|date_of_birth|education|city/.test(field)) categories.add("Basic information");
    if (/children|family/.test(field)) categories.add("Household information");
    if (/housing|owns_car|owns_property/.test(field)) categories.add("Housing information");
    if (/income|employment|occupation|organization|contract/.test(field)) categories.add("Income & employment");
  }
  return [...categories];
}

export function friendlyFeatureLabel(feature: string): string {
  const labels: Record<string, string> = {
    fd: "Fixed Deposit (FD)",
    rd: "Recurring Deposit (RD)",
    sip: "Systematic Investment Plan (SIP)",
    ppf: "Public Provident Fund (PPF)",
    nps: "National Pension System (NPS)",
    emi: "Monthly EMI",
    savings_rate: "Savings Rate",
    cash_flow_negative_months: "Months with Negative Cash Flow",
    bureau_debt_amount: "Outstanding Credit Debt",
    insurance_payment_consistency: "Insurance Payment Consistency",
    employment_years: "Employment Stability",
    monthly_income: "Monthly Income",
    current_dti: "Debt-to-Income Ratio",
    bureau_dti: "Credit Debt-to-Income Ratio",
    cash_flow_mean: "Average Monthly Cash Flow",
    cash_flow_std: "Cash Flow Variation",
    cash_flow_min: "Lowest Monthly Cash Flow",
    total_card_drawings: "Credit Card Spending",
    total_card_payments: "Credit Card Payments",
    avg_minimum_payment: "Average Minimum Credit Card Payment",
    avg_credit_utilisation: "Credit Utilisation",
    bureau_account_count: "Credit Accounts",
    bureau_overdue_amount: "Overdue Credit Payments",
    total_late_payments: "Late Payments",
    total_on_time_payments: "On-time Payments",
    food_expense: "Food Spending",
    rent_expense: "Housing Costs",
    health_insurance: "Health Insurance",
    life_insurance: "Life Insurance",
    fd_amount: "Fixed Deposits",
    rd_contribution: "Recurring Deposits",
    sip_contribution: "Monthly Investment Contributions",
    mutual_fund_balance: "Mutual Fund Balance",
    ppf_contribution: "Provident Fund Contributions",
    nps_contribution: "Pension Contributions",
  };
  return labels[feature] ?? feature.replace(/_/g, " ").replace(/\b\w/g, char => char.toUpperCase());
}
