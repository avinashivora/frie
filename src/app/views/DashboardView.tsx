import { useEffect, useState } from "react";
import { AlertTriangle, Briefcase, ChevronRight, DollarSign, Info, TrendingUp } from "lucide-react";
import { buildFeatures, fetchProfile, listFeatures, type ProfileEnvelope, type StoredFeature } from "../../services/api";
import { DemoPills, Stat, fmtFeature, yearsFeature } from "../components/shared";
import { FullPredictionCard } from "../components/shared";
import { CurrentIndicatorPanel, RecommendationList } from "./PortfolioViews";
import type { CustomerFeatureMap } from "../../services/api";
import type { View } from "../App";

function mapByName(rows: StoredFeature[] | null): CustomerFeatureMap | null {
  if (!rows) return null;
  const out: CustomerFeatureMap = {};
  for (const row of rows) {
    if (row.value_num !== null && row.value_num !== undefined) out[row.feature_name] = row.value_num;
    else if (row.value_text !== null && row.value_text !== undefined) out[row.feature_name] = row.value_text;
  }
  return out;
}

function DeveloperFeatureInspector() {
  const [features, setFeatures] = useState<StoredFeature[] | null>(null);
  useEffect(() => { listFeatures().then(setFeatures).catch(() => setFeatures([])); }, []);
  return <details className="bg-white rounded-xl border border-slate-300 p-5"><summary className="cursor-pointer text-[12px] font-semibold text-slate-600">Developer feature inspector</summary><div className="mt-3 space-y-1 max-h-72 overflow-y-auto">{features === null ? <p className="text-[12px] text-slate-500">Loading diagnostics…</p> : features.map(row => <div key={row.feature_name} className="flex gap-3 text-[11px]"><span className="w-56 shrink-0 truncate font-mono">{row.feature_name}</span><span className="flex-1 truncate">{row.value_num ?? row.value_text ?? "—"}</span><span className="text-slate-400">{row.provenance}</span></div>)}</div></details>;
}

export default function DashboardView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [profileState, setProfileState] = useState<ProfileEnvelope | "loading" | "error">("loading");
  const [snapshot, setSnapshot] = useState<CustomerFeatureMap | null>(null);

  useEffect(() => {
    let live = true;
    const refreshProfile = () => fetchProfile().then(result => { if (live) setProfileState(result); }).catch(() => { if (live) setProfileState("error"); });
    const refreshFeatures = () => buildFeatures().then(() => listFeatures()).then(rows => { if (live) setSnapshot(mapByName(rows)); }).catch(() => { if (live) setSnapshot(null); });
    void refreshProfile(); void refreshFeatures();
    window.addEventListener("frie:features-built", refreshFeatures);
    window.addEventListener("frie:data-changed", refreshProfile);
    window.addEventListener("frie:data-changed", refreshFeatures);
    return () => { live = false; window.removeEventListener("frie:features-built", refreshFeatures); window.removeEventListener("frie:data-changed", refreshProfile); window.removeEventListener("frie:data-changed", refreshFeatures); };
  }, []);

  const profileBanner = profileState === "loading"
    ? null
    : profileState === "error" || !profileState
      ? { text: "Sign in again to sync your profile status.", action: false }
      : profileState.completeness.completed >= profileState.completeness.required
        ? { text: "Profile complete — continue reviewing your financial data and readiness.", action: true }
        : { text: "Complete your profile to continue — add your basic, household, housing, and employment information.", action: true };

  return (
    <div className="space-y-6">
      <DemoPills />
      {profileBanner && (
        <button
          onClick={() => profileBanner.action && onNavigate("profile")}
          className="w-full text-left bg-white rounded-xl border border-[#F1F5F9] px-5 py-3.5 flex items-center gap-3 hover:border-blue-200 transition-colors"
        >
          <Info size={15} className="text-[#3B82F6] shrink-0" />
          <p className="text-[13px] font-semibold text-[#0F172A] flex-1">{profileBanner.text}</p>
          {profileBanner.action && <ChevronRight size={14} className="text-slate-300 shrink-0" />}
        </button>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <FullPredictionCard onCompleteSource={source => onNavigate(source === "profile" || source === "income" ? "profile" : "documents")} />

        <div className="lg:col-span-2 flex flex-col gap-2">
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Financial Snapshot — your stored data</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Stat title="Monthly Income"  value={fmtFeature(snapshot, "monthly_income")}  sub="Your stated income" icon={DollarSign} variant="green" />
            <Stat title="Monthly Savings" value={fmtFeature(snapshot, "monthly_savings")} sub="From your statements" icon={TrendingUp} variant="blue" />
            <Stat title="Employment"      value={yearsFeature(snapshot, "employment_years")} sub="From your start date" icon={Briefcase} variant="amber" />
            <Stat title="Credit Debt"     value={fmtFeature(snapshot, "bureau_debt_amount")} sub="From credit records" icon={AlertTriangle} variant="red" />
          </div>
        </div>
      </div>
      <CurrentIndicatorPanel />
      <RecommendationList limit={3} />
      {new URLSearchParams(window.location.search).get("debug") === "features" && <DeveloperFeatureInspector />}
    </div>
  );
}


