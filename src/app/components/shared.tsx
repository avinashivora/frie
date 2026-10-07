import { useEffect, useState } from "react";
import { CheckCircle2, Circle } from "lucide-react";
import type {
  AssessmentSource,
  AssessmentStatus,
  AssessmentRecord,
  BankImportSummary,
  CustomerFeatureMap,
  LocalExplanation,
  ReliabilityLevel,
} from "../../services/api";
import {
  FrieApiError,
  buildFeatures,
  fetchAssessmentStatus,
  fetchLatestAssessment,
  fetchLocalExplanation,
  importBankTransactions,
  createAssessment,
} from "../../services/api";
import {
  friendlyFeatureLabel,
  type ReadinessSourceKey,
} from "../readinessPresentation";

export function fmt(n: number) {
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(1)}Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  if (n >= 1000) return `₹${(n / 1000).toFixed(0)}K`;
  return `₹${n}`;
}
function featureNumber(
  features: CustomerFeatureMap | null,
  key: string,
): number | null {
  const value = features?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
export function fmtFeature(f: CustomerFeatureMap | null, k: string) {
  const n = featureNumber(f, k);
  return n === null ? "—" : fmt(n);
}
export function yearsFeature(f: CustomerFeatureMap | null, k: string) {
  const n = featureNumber(f, k);
  return n === null ? "—" : `${n.toFixed(1)} yrs`;
}
export function decimalFeature(f: CustomerFeatureMap | null, k: string) {
  const n = featureNumber(f, k);
  return n === null ? "—" : n.toFixed(2);
}
export function pctFeature(f: CustomerFeatureMap | null, k: string) {
  const n = featureNumber(f, k);
  return n === null ? "—" : `${(n * 100).toFixed(1)}%`;
}
export function reliabilityColor(level: ReliabilityLevel) {
  return level === "Excellent"
    ? "#10B981"
    : level === "Good"
      ? "#3B82F6"
      : level === "Average"
        ? "#F59E0B"
        : "#EF4444";
}
export function reliabilityBadgeCls(level: ReliabilityLevel) {
  return level === "Excellent"
    ? "bg-emerald-50 text-emerald-700 border-emerald-100"
    : level === "Good"
      ? "bg-blue-50 text-blue-700 border-blue-100"
      : level === "Average"
        ? "bg-amber-50 text-amber-700 border-amber-100"
        : "bg-red-50 text-red-700 border-red-100";
}
export function Stat({
  title,
  value,
  sub,
  icon: Icon,
  variant = "blue",
}: {
  title: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  variant?: string;
}) {
  const cls: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
    red: "bg-red-50 text-red-600",
  };
  return (
    <div className="bg-white rounded-xl border border-[#F1F5F9] p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500 font-medium">{title}</p>
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center ${cls[variant] || cls.blue}`}
        >
          <Icon size={16} />
        </div>
      </div>
      <div>
        <p className="text-[22px] font-extrabold text-[#0F172A]">{value}</p>
        {sub && <p className="text-[11px] text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}
export function DemoPills() {
  return (
    <div className="flex gap-2">
      <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-[#0F172A] text-white">
        FRIE prototype
      </span>
      <span className="text-[11px] px-2.5 py-1 rounded-full bg-white border text-slate-500">
        Demo experience
      </span>
    </div>
  );
}

export function ScoreGauge({
  score,
  level,
}: {
  score: number;
  level: ReliabilityLevel;
}) {
  const progress = Math.max(0, Math.min(100, score));
  return (
    <div
      className="relative mx-auto w-52"
      role="img"
      aria-label={`FRIE score ${score.toFixed(1)} out of 100, ${level}`}
    >
      <svg viewBox="0 0 220 130" className="w-full" aria-hidden="true">
        <path
          d="M 20 110 A 90 90 0 0 1 200 110"
          fill="none"
          stroke="#F1F5F9"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 20 110 A 90 90 0 0 1 200 110"
          fill="none"
          stroke={reliabilityColor(level)}
          strokeWidth="14"
          strokeLinecap="round"
          pathLength="100"
          strokeDasharray={`${progress} 100`}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-1 text-center">
        <p className="text-4xl font-extrabold text-slate-900">
          {score.toFixed(1)}
        </p>
        <p
          className="mt-1 text-xs font-semibold"
          style={{ color: reliabilityColor(level) }}
        >
          {level}
        </p>
      </div>
    </div>
  );
}

export function BankImportCard({ onImported }: { onImported?: () => void }) {
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<BankImportSummary | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError("");
    try {
      setResult(await importBankTransactions(file));
      onImported?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bank import failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="rounded-xl border bg-white p-5 space-y-3">
      <h3 className="text-sm font-bold">Import bank transactions</h3>
      <p className="text-xs text-slate-500">
        Upload CSV, Excel, or TXT transaction data.
      </p>
      <form onSubmit={submit} className="flex flex-wrap gap-3">
        <input
          type="file"
          accept=".csv,.xlsx,.xls,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          disabled={!file || busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
        >
          {busy ? "Uploading…" : "Upload bank file"}
        </button>
      </form>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {result && (
        <p role="status" className="text-sm text-emerald-700">
          Imported {result.transactions_imported} transactions.
        </p>
      )}
    </section>
  );
}

export function FullPredictionCard({
  onCompleteSource,
}: {
  onCompleteSource?: (source: ReadinessSourceKey) => void;
}) {
  const [status, setStatus] = useState<AssessmentStatus | null>(null),
    [result, setResult] = useState<AssessmentRecord | null>(null),
    [stale, setStale] = useState(false),
    [explanation, setExplanation] = useState<LocalExplanation | null>(null),
    [explanationError, setExplanationError] = useState(""),
    [loading, setLoading] = useState(true),
    [predicting, setPredicting] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [s, a] = await Promise.all([
          fetchAssessmentStatus(),
          fetchLatestAssessment(),
        ]);
        if (active) {
          setStatus(s);
          setResult(a);
          setStale(Boolean(a?.stale));
          setError("");
        }
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Unable to load FRIE readiness.",
          );
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const refresh = () => void load();
    window.addEventListener("frie:data-changed", refresh);
    return () => {
      active = false;
      window.removeEventListener("frie:data-changed", refresh);
    };
  }, []);
  async function generate() {
    if (predicting) return;
    setError("");
    setPredicting(true);
    try {
      await buildFeatures();
      window.dispatchEvent(new Event("frie:features-built"));
      const next = await fetchAssessmentStatus();
      setStatus(next);
      if (!next.can_assess) {
        setResult(null);
        setStale(false);
        setError(next.message);
        return;
      }
      const assessment = await createAssessment();
      setResult(assessment);
      setStale(false);
      setExplanation(null);
      window.dispatchEvent(new Event("frie:assessment-created"));
    } catch (e) {
      setError(
        e instanceof FrieApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "FRIE assessment failed.",
      );
    } finally {
      setPredicting(false);
      setLoading(false);
    }
  }
  const shown = stale ? null : result,
    canAssess = status?.can_assess ?? false,
    complete = status?.assessment_state === "complete",
    estimated = shown?.assessment_state === "estimated";
  return (
    <div className="bg-white rounded-xl border border-[#F1F5F9] p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold">
          {shown
            ? estimated
              ? "Estimated FRIE Score"
              : "FRIE Score"
            : "FRIE Assessment"}
        </h3>
        <span
          className={`text-[11px] px-2.5 py-1 rounded-full border ${loading ? "bg-slate-50 text-slate-500" : complete ? "bg-emerald-50 text-emerald-700" : canAssess ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}
        >
          {loading
            ? "Checking your information…"
            : complete
              ? "Ready to assess"
              : canAssess
                ? "Assessment available"
                : "Information needed"}
        </span>
      </div>
      {!loading && !canAssess && status && (
        <div className="space-y-3">
          <div>
            <p className="text-[15px] font-bold">
              Your FRIE Score isn’t ready yet
            </p>
            <p className="mt-1 text-xs text-slate-500">{status.message}</p>
          </div>
          <SourceReadinessCards
            sources={status.sources}
            onCompleteSource={onCompleteSource}
          />
        </div>
      )}
      {!loading && canAssess && status?.assessment_state === "estimated" && (
        <div className="space-y-3">
          <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
            <p className="text-sm font-bold text-blue-800">
              FRIE assessment available
            </p>
            <p className="mt-1 text-xs text-blue-700">
              Based on the financial information currently available.
            </p>
          </div>
          <SourceReadinessCards
            sources={status.sources}
            onCompleteSource={onCompleteSource}
          />
        </div>
      )}
      {!loading && complete && (
        <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
          <p className="text-sm font-bold text-emerald-800">
            ✓ Financial information complete
          </p>
          <p className="mt-1 text-xs text-emerald-700">
            Your profile and financial information are ready to generate your
            FRIE Score.
          </p>
        </div>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-red-100 bg-red-50 p-3 text-xs text-red-700"
        >
          {error}
        </p>
      )}
      {stale && result && (
        <p
          role="status"
          className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
        >
          Your financial information has changed. Recalculate your FRIE
          assessment.
        </p>
      )}
      {!loading && canAssess && (
        <button
          type="button"
          onClick={generate}
          disabled={predicting}
          className="rounded-lg bg-[#0F172A] px-6 py-2.5 text-[13px] font-semibold text-white disabled:opacity-60"
        >
          {predicting
            ? "Preparing your assessment…"
            : stale
              ? "Recalculate FRIE Score"
              : shown
                ? "Generate another assessment"
                : status?.assessment_state === "estimated"
                  ? "Generate FRIE Assessment"
                  : "Generate FRIE Score"}
        </button>
      )}
      {shown && (
        <div className="space-y-2 rounded-xl border border-emerald-100 bg-emerald-50 p-4">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase text-emerald-800">
              {estimated ? "Estimated FRIE Score" : "FRIE Score"}
            </p>
            <span
              className={`rounded-full border px-2 py-1 text-[11px] ${reliabilityBadgeCls(shown.reliability_level)}`}
            >
              {shown.reliability_level}
            </span>
          </div>
          <ScoreGauge
            score={shown.frie_score}
            level={shown.reliability_level}
          />
          {estimated && (
            <p className="text-xs text-slate-600">
              Based on the financial information currently available.
            </p>
          )}
          <p className="text-[11px] text-slate-500">
            Assessed {new Date(shown.created_at).toLocaleString()} · FRIE
            prototype assessment
          </p>
          <p className="text-[11px] text-slate-500">
            Prototype score approximation. Reliability bands are prototype
            calibration labels, not regulatory standards.
          </p>
          <button
            className="text-xs font-semibold text-blue-700"
            onClick={async () => {
              setExplanationError("");
              try {
                setExplanation(await fetchLocalExplanation());
              } catch (e) {
                setExplanationError(
                  e instanceof Error
                    ? e.message
                    : "Unable to load explanation.",
                );
              }
            }}
          >
            Why this score?
          </button>
          {explanationError && (
            <p role="alert" className="text-xs text-red-700">
              {explanationError}
            </p>
          )}
          {explanation && (
            <div
              className="grid gap-3 sm:grid-cols-2"
              aria-label="Assessment explanation"
            >
              {[
                {
                  label: "Factors that raised your score",
                  rows: explanation.top_positive,
                },
                {
                  label: "Factors that lowered your score",
                  rows: explanation.top_negative,
                },
              ].map((g) => (
                <div key={g.label} className="rounded-lg bg-white/70 p-3">
                  <p className="mb-2 text-[11px] font-bold text-slate-600">
                    {g.label}
                  </p>
                  {g.rows.slice(0, 5).map((item) => (
                    <div
                      key={item.feature}
                      className="flex justify-between gap-2 py-1 text-[11px]"
                    >
                      <span>
                        {friendlyFeatureLabel(item.feature)} ·{" "}
                        {String(item.value ?? "Limited information")}
                      </span>
                      <strong>
                        {item.contribution > 0 ? "+" : ""}
                        {item.contribution.toFixed(3)}
                      </strong>
                    </div>
                  ))}
                </div>
              ))}
              <p className="text-[11px] text-slate-500 sm:col-span-2">
                These factors describe how information affected this assessment.
                They do not establish cause and effect.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
function SourceReadinessCards({
  sources,
  onCompleteSource,
}: {
  sources: AssessmentSource[];
  onCompleteSource?: (source: ReadinessSourceKey) => void;
}) {
  const labels = {
    complete: "Complete",
    required: "Required",
    recommended: "Recommended",
    optional: "Optional",
    unknown: "Not provided yet",
  } as const;
  const accepted: Record<AssessmentSource["key"], string> = {
    profile: "Profile details",
    income: "Profile details or salary / income documents",
    bank: "CSV, Excel, PDF, or image",
    credit: "PDF, PNG, or JPEG",
    insurance: "Profile declaration or PDF, PNG, or JPEG",
    investments: "Profile declarations or PDF, PNG, or JPEG",
    loans: "Profile declaration or PDF, PNG, or JPEG",
  };
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {sources.map((source) => {
        const done = source.status === "complete",
          action =
            source.status === "required" ||
            source.status === "recommended" ||
            source.status === "unknown";
        return (
          <div
            key={source.key}
            className={`rounded-lg border p-3 ${done ? "border-emerald-100 bg-emerald-50/50" : action ? "border-amber-100 bg-amber-50/50" : "border-slate-100 bg-slate-50"}`}
          >
            <div className="flex items-center gap-2">
              {done ? (
                <CheckCircle2 size={16} className="text-emerald-600" />
              ) : (
                <Circle size={16} className="text-slate-400" />
              )}
              <p className="text-xs font-semibold text-slate-800">
                {source.title}
              </p>
              <span className="ml-auto text-[10px] text-slate-500">
                {labels[source.status]}
              </span>
            </div>
            {!done && (
              <>
                <p className="mt-2 text-[11px] text-slate-600">
                  {source.description}
                </p>
                <p className="mt-1 text-[10px] text-slate-400">
                  Accepted: {accepted[source.key]}
                </p>
                {action && onCompleteSource && (
                  <button
                    onClick={() => onCompleteSource(source.key)}
                    className="mt-2 text-[11px] font-semibold text-blue-700"
                  >
                    {source.key === "profile"
                      ? "Complete Profile"
                      : "Add information"}{" "}
                    →
                  </button>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
