import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle } from "lucide-react";
import {
  FrieApiError, fetchFinancialStatus, fetchProfile, loadSession, saveFinancialStatus, saveProfile,
  type FinancialStatus, type ProfileData, type ProfileEnvelope,
} from "../../services/api";
import type { View } from "../App";
import { profileMissingCategories } from "../readinessPresentation";

// ============================================
// Extracted components (outside ProfileView to prevent remounts)
// ============================================

const PROFILE_LABELS: Record<string, string> = {
  gender: "Gender", date_of_birth: "Date of Birth", children_count: "Children",
  family_size: "Family Size", family_status: "Family Status", education_level: "Education",
  housing_type: "Housing", owns_car: "Owns Car", owns_property: "Owns Property",
  income_type: "Income Type", occupation: "Occupation", organization_type: "Organization Type",
  contract_type: "Contract Type", city: "City", monthly_income: "Monthly Income (₹)",
  employment_start: "Employment Start Date",
};

const PROFILE_DROPDOWNS: Record<string, string[]> = {
  gender: ["F", "M"],
  family_status: ["Civil marriage", "Married", "Separated", "Single / not married", "Widow"],
  education_level: ["Higher education", "Incomplete higher", "Lower secondary", "Secondary / secondary special"],
  housing_type: ["Co-op apartment", "House / apartment", "Municipal apartment", "Office apartment", "Rented apartment", "With parents"],
  owns_car: ["N", "Y"],
  owns_property: ["N", "Y"],
  income_type: ["Commercial associate", "Pensioner", "State servant", "Working"],
  occupation: ["Accountants", "Cleaning staff", "Cooking staff", "Core staff", "Drivers", "HR staff", "High skill tech staff", "IT staff", "Laborers", "Low-skill Laborers", "Managers", "Medicine staff", "Private service staff", "Realty agents", "Sales staff", "Secretaries", "Security staff", "Waiters/barmen staff"],
  organization_type: ["Advertising", "Agriculture", "Bank", "Business Entity Type 1", "Business Entity Type 2", "Business Entity Type 3", "Cleaning", "Construction", "Electricity", "Emergency", "Government", "Hotel", "Housing", "Industry: type 1", "Industry: type 10", "Industry: type 11", "Industry: type 12", "Industry: type 2", "Industry: type 3", "Industry: type 5", "Industry: type 7", "Industry: type 9", "Insurance", "Kindergarten", "Legal Services", "Medicine", "Military", "Mobile", "Other", "Police", "Postal", "Realtor", "Restaurant", "School", "Security", "Security Ministries", "Self-employed", "Services", "Telecom", "Trade: type 1", "Trade: type 2", "Trade: type 3", "Trade: type 7", "Transport: type 1", "Transport: type 2", "Transport: type 3", "Transport: type 4", "University", "XNA"],
  contract_type: ["Cash loans", "Revolving loans"],
};

function profileYearsBetween(from: string): number | null {
  const start = new Date(`${from}T00:00:00`);
  if (Number.isNaN(start.getTime())) return null;
  const now = new Date();
  let years = now.getFullYear() - start.getFullYear();
  const anniversary = new Date(start);
  anniversary.setFullYear(now.getFullYear());
  if (anniversary > now) years -= 1;
  return years;
}

function Field({ field, kind, required, values, set, PROFILE_LABELS, PROFILE_DROPDOWNS }: {
  field: string;
  kind: "text" | "number" | "date" | "select";
  required?: boolean;
  values: Record<string, string>;
  set: (field: string, value: string) => void;
  PROFILE_LABELS: Record<string, string>;
  PROFILE_DROPDOWNS: Record<string, string[]>;
}) {
  const options = PROFILE_DROPDOWNS[field];
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={`profile-${field}`} className="text-[12px] font-semibold text-slate-600">
        {PROFILE_LABELS[field] ?? field}
        {required && <span className="text-red-500"> *</span>}
      </label>
      {kind === "select" && options ? (
        <select
          id={`profile-${field}`}
          value={values[field] ?? ""}
          onChange={e => set(field, e.target.value)}
          className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-[8px] px-3 py-2.5 text-[13px] text-[#334155] outline-none focus-within:border-blue-300"
        >
          <option value="">Not provided</option>
          {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      ) : (
        <input
          id={`profile-${field}`}
          type={kind === "number" ? "number" : kind}
          value={values[field] ?? ""}
          onChange={e => set(field, e.target.value)}
          placeholder="Not provided"
          className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-[8px] px-3 py-2.5 text-[13px] text-[#334155] placeholder:text-[#94A3B8] outline-none focus-within:border-blue-300"
        />
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">{title}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>
    </div>
  );
}

function TriState({ label, value, onChange, options }: {
  label: string;
  value: string | null | undefined;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3 py-2.5 border-b border-[#F1F5F9] last:border-0">
      <p className="text-[13px] font-semibold text-[#0F172A]">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {options.map(opt => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all ${
              value === opt.value
                ? "bg-[#0F172A] text-white"
                : "bg-[#F8FAFC] border border-[#F1F5F9] text-slate-500 hover:bg-slate-100"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const YES_NO_UNKNOWN = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "None" },
  { value: "unknown", label: "I don't know" },
];

export default function ProfileView({ onNavigate }: { onNavigate: (v: View) => void }) {
  const session = loadSession();
  const [values, setValues]       = useState<Record<string, string>>({});
  const [baseline, setBaseline]   = useState<Record<string, string>>({});
  const [envelope, setEnvelope]   = useState<ProfileEnvelope | null>(null);
  const [decls, setDecls]         = useState<FinancialStatus>({});
  const [declsBaseline, setDeclsBaseline] = useState<FinancialStatus>({});
  const [declsSaving, setDeclsSaving]     = useState(false);
  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState("");
  const [savedAt, setSavedAt]     = useState("");

  function toForm(profile: ProfileData | null): Record<string, string> {
    const out: Record<string, string> = {};
    if (!profile) return out;
    for (const [key, value] of Object.entries(profile)) {
      if (key === "id" || key === "user_id" || key === "created_at" || key === "updated_at") continue;
      if (value === null || value === undefined) continue;
      out[key] = String(value);
    }
    return out;
  }

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    fetchProfile()
      .then(result => {
        if (!live) return;
        const form = toForm(result?.profile ?? null);
        setValues(form);
        setBaseline(form);
        setEnvelope(result);
        setLoading(false);
      })
      .catch(err => {
        if (!live) return;
        setError(err instanceof FrieApiError && err.message ? err.message : "Unable to load the profile.");
        setLoading(false);
      });
    fetchFinancialStatus()
      .then(status => {
        if (!live) return;
        const form: FinancialStatus = status ?? {};
        setDecls(form);
        setDeclsBaseline(form);
      })
      .catch(() => { if (live) { setDecls({}); setDeclsBaseline({}); } });
    return () => { live = false; };
  }, []);

  const dirty = JSON.stringify(values) !== JSON.stringify(baseline);

  function set(key: string, value: string) {
    setValues(v => ({ ...v, [key]: value }));
    setSavedAt("");
  }

  function clientIssues(): string[] {
    const issues: string[] = [];
    const required = ["gender", "date_of_birth", "family_status", "education_level", "housing_type", "city",
      "owns_car", "owns_property", "income_type", "occupation", "organization_type", "contract_type", "monthly_income"];
    for (const key of required) {
      if (!values[key]?.trim()) issues.push(`${PROFILE_LABELS[key] ?? key} is required.`);
    }
    const income = values.monthly_income?.trim();
    if (income && (!Number.isFinite(Number(income)) || Number(income) <= 0)) {
      issues.push("Monthly Income must be a number greater than zero.");
    }
    for (const key of ["children_count", "family_size"]) {
      const raw = values[key]?.trim();
      if (raw && (!/^\d+$/.test(raw) || Number(raw) < (key === "family_size" ? 1 : 0))) {
        issues.push(`${PROFILE_LABELS[key] ?? key} must be a whole number.`);
      }
    }
    const today = new Date().toISOString().slice(0, 10);
    if (values.date_of_birth && values.date_of_birth > today) {
      issues.push("Date of Birth must not be in the future.");
    }
    if (values.date_of_birth) {
      const age = profileYearsBetween(values.date_of_birth);
      if (age !== null && age > 120) issues.push("Date of Birth implies an unreasonable age.");
    }
    if (values.employment_start && values.employment_start > today) {
      issues.push("Employment Start Date must not be in the future.");
    }
    return issues;
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (saving) return;
    setError("");
    setSavedAt("");
    const issues = clientIssues();
    if (issues.length > 0) {
      setError(issues.slice(0, 3).join(" "));
      return;
    }
    setSaving(true);
    try {
      const numericKeys = ["children_count", "family_size", "monthly_income"];
      const payload: ProfileData = {};
      for (const [key, raw] of Object.entries(values)) {
        const trimmed = raw.trim();
        if (!trimmed) {
          (payload as Record<string, null>)[key] = null;
        } else if (numericKeys.includes(key)) {
          const num = Number(trimmed);
          (payload as Record<string, number | null>)[key] = Number.isFinite(num) ? num : null;
        } else {
          (payload as Record<string, string>)[key] = trimmed;
        }
      }
      const result = await saveProfile(payload);
      const form = toForm(result?.profile ?? null);
      setValues(form);
      setBaseline(form);
      setEnvelope(result);
      setSavedAt("Profile saved successfully.");
    } catch (err) {
      setError(err instanceof FrieApiError && err.message ? err.message : "Unable to save the profile.");
    } finally {
      setSaving(false);
    }
  }

  const completeness = envelope?.completeness ?? null;
  const agePreview = values.date_of_birth ? profileYearsBetween(values.date_of_birth) : null;
  const employmentPreview = values.employment_start ? profileYearsBetween(values.employment_start) : null;

  function setDecl<K extends keyof FinancialStatus>(key: K, value: FinancialStatus[K]) {
    setDecls(current => ({ ...current, [key]: value }));
  }

  const declsDirty = JSON.stringify(decls) !== JSON.stringify(declsBaseline);

async function handleDeclsSave() {
  if (declsSaving || loading) return;
  setError("");
  setDeclsSaving(true);
  try {
    const saved = await saveFinancialStatus(decls);
    setDecls(saved);
    setDeclsBaseline(saved);
    setSavedAt("Financial availability saved.");
  } catch (err) {
    setError(err instanceof FrieApiError && err.message ? err.message : "Unable to save the financial status.");
  } finally {
    setDeclsSaving(false);
  }
}

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="bg-white rounded-xl border border-[#F1F5F9] p-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-[#0F172A] flex items-center justify-center text-white text-[20px] font-bold shrink-0" style={{ fontFamily: "Outfit, sans-serif" }}>
            {(session?.email ?? "?").charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-[20px] font-extrabold text-[#0F172A]" style={{ fontFamily: "Outfit, sans-serif" }}>{session?.email.split("@")[0] ?? "FRIE User"}</h2>
            <p className="text-[13px] text-slate-500 truncate">{session?.email ?? ""}</p>
            <span className="inline-block mt-1.5 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
              Authenticated session
            </span>
          </div>
        </div>

        <div className="mt-5 pt-5 border-t border-[#F1F5F9]">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">Profile setup</p>
            <p className="text-[12px] font-bold text-[#0F172A]">
              {loading ? "Checking…" : completeness?.missing.length ? "More information needed" : "Complete"}
            </p>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-[#3B82F6] transition-all"
              style={{ width: `${loading ? 0 : (completeness?.percentage ?? 0)}%` }}
            />
          </div>
          {!loading && completeness && completeness.missing.length > 0 && (
            <p className="text-[12px] text-slate-500 mt-2">
              Complete these sections: {profileMissingCategories(completeness.missing).join(", ") || "Profile information"}.
            </p>
          )}
          {!loading && completeness && completeness.missing.length === 0 && (
            <p className="text-[12px] font-semibold text-emerald-600 mt-2">All profile fields complete.</p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#F1F5F9] p-6 flex items-center justify-between gap-4">
        <div><h3 className="text-[14px] font-bold text-[#0F172A]">Next: Add financial information</h3><p className="text-[12px] text-slate-500 mt-1">Add income, bank, credit, insurance, investment, and loan details to prepare your FRIE assessment.</p></div>
        <button type="button" onClick={() => onNavigate("documents")} className="shrink-0 bg-[#0F172A] hover:bg-slate-800 text-white font-semibold text-[12px] px-4 py-2.5 rounded-lg">Continue</button>
      </div>

      <form onSubmit={handleSave} className="bg-white rounded-xl border border-[#F1F5F9] p-6 space-y-6">
        <div>
          <h3 className="text-[14px] font-bold text-[#0F172A]">Customer Profile</h3>
          <p className="text-[12px] text-slate-500 mt-1">
            Age{agePreview !== null ? ` (currently ${agePreview})` : ""} and employment duration
            {employmentPreview !== null ? ` (currently ${employmentPreview} yrs)` : ""} are calculated from these details.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center gap-3 py-6">
            <div className="w-5 h-5 border-2 border-[#0F172A] border-t-transparent rounded-full animate-spin" />
            <p className="text-[13px] font-semibold text-slate-600">Loading profile...</p>
          </div>
        ) : (
          <div className="space-y-6">
            <Section title="Personal Information">
              <Field field="gender" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="date_of_birth" kind="date" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="family_status" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="education_level" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
            </Section>
            <Section title="Family & Housing">
              <Field field="children_count" kind="number" values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="family_size" kind="number" values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="housing_type" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="city" kind="text" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="owns_car" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="owns_property" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
            </Section>
            <Section title="Employment">
              <Field field="income_type" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="occupation" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="organization_type" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="employment_start" kind="date" values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
              <Field field="contract_type" kind="select" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
            </Section>
            <Section title="Financial Information">
              <Field field="monthly_income" kind="number" required values={values} set={set} PROFILE_LABELS={PROFILE_LABELS} PROFILE_DROPDOWNS={PROFILE_DROPDOWNS} />
            </Section>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 mt-4">
            <AlertCircle size={14} className="text-red-500 shrink-0 mt-0.5" />
            <p className="text-red-600 text-[13px]">{error}</p>
          </div>
        )}
        {savedAt && (
          <div className="flex items-start gap-2.5 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2.5 mt-4">
            <CheckCircle size={14} className="text-emerald-500 shrink-0 mt-0.5" />
            <p className="text-emerald-700 text-[13px]">{savedAt}</p>
          </div>
        )}

        <div className="flex items-center justify-between mt-5">
          <p className="text-[12px] text-slate-400">{dirty && !loading ? "Unsaved changes." : ""}</p>
          <button
            type="submit"
            disabled={loading || saving}
            className="bg-[#0F172A] hover:bg-slate-800 disabled:opacity-60 text-white font-semibold text-[13px] px-6 py-2.5 rounded-lg transition-colors"
          >
            {saving ? "Saving..." : "Save Profile"}
          </button>
        </div>
      </form>

      <div className="bg-white rounded-xl border border-[#F1F5F9] p-6">
        <h3 className="text-[14px] font-bold text-[#0F172A]">Financial Availability</h3>
        <p className="text-[12px] text-slate-500 mt-1 mb-2">
          Declare which products you hold. "None" means confirmed absent; "I don't know" leaves the data honestly unknown — never zero.
        </p>
        <TriState
          label="Do you currently have a loan?"
          value={decls.has_loan}
          onChange={value => setDecl("has_loan", value)}
          options={YES_NO_UNKNOWN}
        />
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3 py-2.5 border-b border-[#F1F5F9]">
          <p className="text-[13px] font-semibold text-[#0F172A]">Do you have insurance?</p>
          <div className="flex flex-wrap gap-1.5 sm:justify-end">
            {[
              { value: "health", label: "Health" },
              { value: "life", label: "Life" },
              { value: "both", label: "Both" },
              { value: "none", label: "None" },
              { value: "unknown", label: "I don't know" },
            ].map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setDecl("insurance_status", opt.value)}
                className={`px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all ${
                  decls.insurance_status === opt.value
                    ? "bg-[#0F172A] text-white"
                    : "bg-[#F8FAFC] border border-[#F1F5F9] text-slate-500 hover:bg-slate-100"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <TriState label="Fixed Deposit (FD)" value={decls.inv_fd} onChange={value => setDecl("inv_fd", value)} options={YES_NO_UNKNOWN} />
        <TriState label="Recurring Deposit (RD)" value={decls.inv_rd} onChange={value => setDecl("inv_rd", value)} options={YES_NO_UNKNOWN} />
        <TriState label="Systematic Investment Plan (SIP)" value={decls.inv_sip} onChange={value => setDecl("inv_sip", value)} options={YES_NO_UNKNOWN} />
        <TriState label="Mutual Fund" value={decls.inv_mutual_fund} onChange={value => setDecl("inv_mutual_fund", value)} options={YES_NO_UNKNOWN} />
        <TriState label="Public Provident Fund (PPF)" value={decls.inv_ppf} onChange={value => setDecl("inv_ppf", value)} options={YES_NO_UNKNOWN} />
        <TriState label="National Pension System (NPS)" value={decls.inv_nps} onChange={value => setDecl("inv_nps", value)} options={YES_NO_UNKNOWN} />
        <div className="flex items-center justify-between mt-4">
          <p className="text-[12px] text-slate-400">{declsDirty ? "Unsaved changes." : ""}</p>
          <button
            type="button"
            onClick={handleDeclsSave}
            disabled={loading || declsSaving}
            className="bg-[#0F172A] hover:bg-slate-800 disabled:opacity-60 text-white font-semibold text-[13px] px-6 py-2.5 rounded-lg transition-colors"
          >
            {declsSaving ? "Saving..." : "Save Availability"}
          </button>
        </div>
      </div>
    </div>
  );
}
