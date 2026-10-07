import { useEffect, useState } from "react";
import { Activity, BarChart2, CheckCircle, CreditCard, DollarSign, Info, Loader2, Percent, TrendingDown, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { FrieApiError, buildFeatures, listFeatures, type StoredFeature } from "../../services/api";
import { decimalFeature, fmtFeature, pctFeature, Stat } from "../components/shared";
import { FullPredictionCard } from "../components/shared";
import type { CustomerFeatureMap } from "../../services/api";
import type { View } from "../App";
import { CurrentIndicatorPanel } from "./PortfolioViews";

function toFeatureMap(rows: StoredFeature[]): CustomerFeatureMap {
  const out: CustomerFeatureMap = {};
  for (const row of rows) {
    if (row.value_num !== null && row.value_num !== undefined) out[row.feature_name] = row.value_num;
    else if (row.value_text !== null && row.value_text !== undefined) out[row.feature_name] = row.value_text;
  }
  return out;
}

export default function AnalysisView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [features, setFeatures] = useState<CustomerFeatureMap | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");

  useEffect(() => {
    let live = true;
    setLoading(true);
    buildFeatures().then(() => listFeatures())
      .then(rows => { if (live) { setFeatures(toFeatureMap(rows)); setLoading(false); } })
      .catch(err => {
        if (!live) return;
        setError(err instanceof FrieApiError && err.message ? err.message : "Unable to load your financial data.");
        setLoading(false);
      });
    return () => { live = false; };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[440px] bg-white rounded-xl border border-[#F1F5F9] p-12">
        <div className="w-14 h-14 border-4 border-[#0F172A] border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-[20px] font-extrabold text-[#0F172A] mb-2" style={{ fontFamily: "Outfit, sans-serif" }}>
          Loading Your Financials
        </h2>
        <p className="text-[14px] text-slate-500 text-center max-w-md">
          Reading your stored profile and document data.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] bg-white rounded-xl border border-[#F1F5F9] p-12 text-center">
        <p className="text-[15px] font-bold text-red-700">Unable to load financial analysis</p>
        <p className="text-[13px] text-slate-500 mt-1">{error}</p>
      </div>
    );
  }

  const hasData = features !== null && Object.keys(features).length > 0;
  if (!hasData) {
    return (
      <div className="space-y-6 max-w-4xl">
        <FullPredictionCard onCompleteSource={source => onNavigate(source === "profile" || source === "income" ? "profile" : "documents")} />
        <div className="flex flex-col items-center justify-center min-h-[300px] bg-white rounded-xl border border-[#F1F5F9] p-12 text-center">
          <p className="text-[18px] font-extrabold text-[#0F172A]" style={{ fontFamily: "Outfit, sans-serif" }}>No financial data yet</p>
          <p className="text-[13px] text-slate-500 mt-2 max-w-md">
            Complete your profile and add financial documents to see your financial analysis here.
          </p>
          <button
            onClick={() => onNavigate("profile")}
            className="mt-5 bg-[#0F172A] hover:bg-slate-800 text-white font-semibold text-[13px] px-6 py-2.5 rounded-lg transition-colors"
          >
            Go to Profile
          </button>
        </div>
      </div>
    );
  }

  const metrics: { label: string; value: string; icon: React.ElementType; variant: string }[] = [
    { label: "Monthly Income",     value: fmtFeature(features, "monthly_income"),        icon: DollarSign,   variant: "green" },
    { label: "Monthly Expenses",   value: fmtFeature(features, "synthetic_total_expense"), icon: TrendingDown, variant: "red"   },
    { label: "Monthly Savings",    value: fmtFeature(features, "monthly_savings"),       icon: TrendingUp,   variant: "blue"  },
    { label: "Savings Balance",    value: fmtFeature(features, "savings_balance"),       icon: CreditCard,   variant: "amber" },
    { label: "Monthly EMI",        value: fmtFeature(features, "synthetic_total_emi"),  icon: CreditCard,   variant: "amber" },
    { label: "Available Surplus",  value: fmtFeature(features, "available_surplus"),     icon: BarChart2,    variant: "blue"  },
    { label: "Savings Rate",       value: pctFeature(features, "savings_rate"),          icon: Percent,      variant: "green" },
    { label: "Debt-to-Income",     value: decimalFeature(features, "current_dti"),       icon: Activity,     variant: "red"   },
  ];

  const chartData = [
    { name: "Income", key: "monthly_income", fill: "#10B981" },
    { name: "Expenses", key: "synthetic_total_expense", fill: "#EF4444" },
    { name: "Savings", key: "monthly_savings", fill: "#3B82F6" },
    { name: "EMI", key: "synthetic_total_emi", fill: "#F59E0B" },
  ].flatMap(({ name, key, fill }) => {
    const value = features?.[key];
    return typeof value === "number" && Number.isFinite(value) ? [{ name, value: Math.round(value / 1000), fill }] : [];
  });
  const chartHasData = chartData.some(entry => entry.value > 0);

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 flex items-center gap-3">
        <CheckCircle size={20} className="text-emerald-500 shrink-0" />
        <div>
          <p className="text-[14px] font-semibold text-emerald-800">Your Financial Data</p>
          <p className="text-[12px] text-emerald-600">Metrics below come only from your stored profile and reviewed documents.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map(({ label, value, icon, variant }) => (
          <Stat key={label} title={label} value={value} icon={icon} variant={variant} />
        ))}
      </div>

      {chartHasData && (
        <div className="bg-white rounded-xl border border-[#F1F5F9] p-6">
          <h3 className="text-[14px] font-bold text-[#0F172A] mb-4">Monthly Financial Breakdown</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} barSize={44}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} axisLine={false} tickLine={false} tickFormatter={v => `₹${v}K`} />
              <Tooltip formatter={(v: number) => [`₹${v}K`, ""]} contentStyle={{ fontSize: 12, border: "1px solid #F1F5F9", borderRadius: 8, boxShadow: "none" }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={`cell-${i}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-xl p-4 flex items-start gap-3">
        <Info size={15} className="text-slate-400 mt-0.5 shrink-0" />
        <p className="text-[12px] text-slate-500">
          Prototype: figures reflect your stored profile and reviewed documents only. Fields without data show as unavailable rather than estimated.
        </p>
      </div>

      <FullPredictionCard onCompleteSource={source => onNavigate(source === "profile" ? "profile" : "documents")} />
      <CurrentIndicatorPanel />
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-start gap-3">
        <Info size={15} className="text-slate-500 mt-0.5 shrink-0" />
        <p className="text-[12px] text-slate-600">The factors shown summarize how your available financial information influenced this assessment. They are explanatory and do not establish cause and effect.</p>
      </div>
    </div>
  );
}
