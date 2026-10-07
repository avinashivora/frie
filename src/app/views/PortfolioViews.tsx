import { useEffect, useState } from "react";
import { Clock3, Info, Lightbulb, Settings2 } from "lucide-react";
import {
  fetchAccount,
  fetchAssessmentHistory,
  fetchLatestAssessment,
  type AssessmentRecord,
  type AuthAccount,
  type FrieRecommendation,
} from "../../services/api";
import { FullPredictionCard } from "../components/shared";
import type { View } from "../App";

const INDICATORS = [
  ["income_stability", "Income Stability"],
  ["cashflow_stability", "Cash-flow Stability"],
  ["payment_discipline", "Payment Discipline"],
  ["savings_discipline", "Savings Discipline"],
  ["commitment_adherence", "Commitment Adherence"],
  ["debt_burden", "Debt Burden"],
  ["financial_stress", "Financial Stress"],
  ["financial_resilience", "Financial Resilience"],
] as const;
const card = "bg-white rounded-xl border border-[#F1F5F9] p-6";

function useCurrentAssessment() {
  const [assessment, setAssessment] = useState<AssessmentRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = () =>
      fetchLatestAssessment()
        .then((value) => {
          if (active) {
            setAssessment(value);
            setError("");
          }
        })
        .catch((err) => {
          if (active)
            setError(
              err instanceof Error
                ? err.message
                : "Unable to load your assessment.",
            );
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    void load();
    window.addEventListener("frie:assessment-created", load);
    window.addEventListener("frie:data-changed", load);
    return () => {
      active = false;
      window.removeEventListener("frie:assessment-created", load);
      window.removeEventListener("frie:data-changed", load);
    };
  }, []);
  return { assessment, loading, error };
}

export function RecommendationList({ limit }: { limit?: number }) {
  const { assessment, loading, error } = useCurrentAssessment();
  const recommendations = assessment?.stale
    ? []
    : (assessment?.recommendations ?? []);
  const displayed = limit ? recommendations.slice(0, limit) : recommendations;
  return (
    <section className={card}>
      <h3 className="text-[14px] font-bold text-[#0F172A]">Recommendations</h3>
      {!limit && assessment && !assessment.stale && (
        <div className="mt-4 grid grid-cols-3 gap-3">
          {(["High", "Medium", "Low"] as const).map((priority) => (
            <div
              key={priority}
              className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 text-center"
            >
              <p
                className={`text-2xl font-extrabold ${priority === "High" ? "text-rose-500" : priority === "Medium" ? "text-amber-500" : "text-emerald-500"}`}
              >
                {
                  recommendations.filter((item) => item.priority === priority)
                    .length
                }
              </p>
              <p className="mt-1 text-xs text-slate-500">{priority} priority</p>
            </div>
          ))}
        </div>
      )}
      {loading ? (
        <p className="mt-4 text-[13px] text-slate-500">
          Loading your latest assessment…
        </p>
      ) : error ? (
        <p role="alert" className="mt-4 text-[13px] text-red-700">
          {error}
        </p>
      ) : !assessment ? (
        <p className="mt-4 text-[13px] text-slate-500">
          Generate a FRIE assessment to see guidance based on your information.
        </p>
      ) : assessment.stale ? (
        <p className="mt-4 text-[13px] text-amber-800">
          Your financial information changed. Recalculate your FRIE Score to
          refresh recommendations.
        </p>
      ) : displayed.length === 0 ? (
        <p className="mt-4 text-[13px] text-slate-500">
          No recommendations are available for this assessment.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {displayed.map((item, index) => (
            <RecommendationItem
              key={`${item.related_indicator}-${index}`}
              item={item}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function RecommendationItem({ item }: { item: FrieRecommendation }) {
  const priorityStyle =
    item.priority === "High"
      ? "bg-rose-50 text-rose-700"
      : item.priority === "Medium"
        ? "bg-amber-50 text-amber-700"
        : "bg-slate-100 text-slate-600";
  return (
    <article className="rounded-lg border border-slate-100 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold text-slate-500">
          {item.category}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${priorityStyle}`}
        >
          Priority: {item.priority}
        </span>
        <span className="ml-auto text-[11px] text-slate-400">
          Related to {item.related_indicator_label}
        </span>
      </div>
      <h4 className="mt-2 text-[13px] font-bold text-[#0F172A]">
        {item.title}
      </h4>
      <p className="mt-1 text-[12px] text-slate-600">{item.description}</p>
      <p className="mt-2 text-[11px] text-slate-500">{item.reason}</p>
    </article>
  );
}

export function ScoreReportView({
  onCompleteSource,
}: {
  onCompleteSource?: (
    source: import("../readinessPresentation").ReadinessSourceKey,
  ) => void;
}) {
  const { assessment, loading, error } = useCurrentAssessment();
  return (
    <div className="space-y-6 max-w-5xl">
      <div className={card}>
        <h2 className="text-[20px] font-extrabold text-[#0F172A]">
          FRIE Score &amp; Report
        </h2>
        <p className="text-[12px] text-slate-500 mt-1">
          Your assessment and source-backed explanation.
        </p>
      </div>
      <FullPredictionCard onCompleteSource={onCompleteSource} />
      <section className={card}>
        <h3 className="text-[14px] font-bold text-[#0F172A] mb-2">
          FRIE Indicator Breakdown
        </h3>
        <p className="text-[12px] text-slate-500 mb-4">
          Each indicator contributes 12.5% to the prototype FRIE framework.
          These are methodology-derived dimensions, separate from the model
          prediction and explanation.
        </p>
        {loading ? (
          <p className="py-3 text-[13px] text-slate-500">Loading indicators…</p>
        ) : error ? (
          <p role="alert" className="py-3 text-[13px] text-red-700">
            {error}
          </p>
        ) : !assessment ? (
          <p className="py-3 text-[13px] text-slate-500">
            Generate a FRIE assessment to view your indicators.
          </p>
        ) : assessment.stale ? (
          <p className="py-3 text-[13px] text-amber-800">
            Your financial information changed. Recalculate your FRIE Score to
            refresh the indicators.
          </p>
        ) : (
          <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {INDICATORS.map(([key, name]) => {
              const detail = assessment.indicator_details?.[key];
              const value = assessment.indicators?.[key] ?? null;
              return (
                <details key={key} className="group py-3">
                  <summary className="list-none cursor-pointer">
                    <div className="flex items-center gap-4">
                      <span className="flex-1 text-[13px] font-semibold text-slate-700">
                        {name}
                      </span>
                      {typeof value === "number" ? (
                        <span className="w-32 text-right text-[12px] font-bold text-slate-800">
                          {value.toFixed(0)}/100
                          {detail?.availability === "LIMITED"
                            ? " · Limited information"
                            : ""}
                        </span>
                      ) : (
                        <span className="text-[12px] text-slate-400">
                          Limited information
                        </span>
                      )}
                    </div>
                    {typeof value === "number" && (
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{
                            width: `${Math.max(0, Math.min(100, value))}%`,
                          }}
                        />
                      </div>
                    )}
                  </summary>
                  {typeof value === "number" && (
                    <div className="mt-3">
                      {detail && (
                        <div className="mt-3 grid gap-2 text-[12px] text-slate-600 sm:grid-cols-2">
                          <p>
                            <strong>Measures:</strong> {detail.measures}
                          </p>
                          <p>
                            <strong>Based on:</strong>{" "}
                            {detail.based_on.join(", ")}
                          </p>
                          <p className="sm:col-span-2">
                            <strong>Prototype methodology:</strong>{" "}
                            {detail.methodology_note}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </details>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

export function CurrentIndicatorPanel() {
  const { assessment, loading, error } = useCurrentAssessment();
  const items = [
    ["income_stability", "Income Stability"],
    ["cashflow_stability", "Cash-flow Stability"],
    ["payment_discipline", "Payment Discipline"],
    ["savings_discipline", "Savings Discipline"],
    ["commitment_adherence", "Commitment Adherence"],
    ["debt_burden", "Debt Burden"],
    ["financial_stress", "Financial Stress"],
    ["financial_resilience", "Financial Resilience"],
  ] as const;
  return (
    <section className={card}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[14px] font-bold text-[#0F172A]">
            FRIE Indicator Breakdown
          </h3>
          <p className="mt-1 text-[11px] text-slate-500">
            Eight methodology dimensions; each contributes 12.5% to the
            prototype framework.
          </p>
        </div>
        {!assessment?.stale && assessment?.assessment_state === "estimated" && (
          <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700">
            Estimated assessment
          </span>
        )}
      </div>
      {loading ? (
        <p className="mt-4 text-xs text-slate-500">Loading indicators…</p>
      ) : error ? (
        <p role="alert" className="mt-4 text-xs text-red-700">
          {error}
        </p>
      ) : !assessment ? (
        <p className="mt-4 text-xs text-slate-500">
          Indicators appear after your first FRIE assessment.
        </p>
      ) : assessment.stale ? (
        <p className="mt-4 text-xs text-amber-800">
          Your financial information changed. Recalculate your assessment to
          refresh these indicators.
        </p>
      ) : (
        <div className="mt-4 grid gap-x-8 sm:grid-cols-2">
          {items.map(([key, label]) => {
            const value = assessment.indicators?.[key] ?? null;
            const detail = assessment.indicator_details?.[key];
            return (
              <div key={key} className="border-b border-slate-100 py-3">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-medium text-slate-700">{label}</span>
                  <span className="font-bold text-slate-700">
                    {typeof value === "number"
                      ? `${value.toFixed(0)}/100`
                      : "Limited information"}
                  </span>
                </div>
                {typeof value === "number" && (
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-blue-500"
                      style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                    />
                  </div>
                )}
                {detail?.availability === "LIMITED" && (
                  <p className="mt-1 text-[10px] text-slate-400">
                    Limited information
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-[10px] text-slate-400">
        Prototype methodology dimensions, separate from the model score and its
        explanation. Not regulatory standards.
      </p>
    </section>
  );
}

export function RecommendationsView() {
  return (
    <div className="space-y-5 max-w-4xl">
      <section className={card}>
        <div className="flex items-center gap-3">
          <Lightbulb className="text-blue-600" size={20} />
          <div>
            <h2 className="text-[20px] font-extrabold text-[#0F172A]">
              Recommendations
            </h2>
            <p className="text-[12px] text-slate-500">
              Informational guidance based on your latest FRIE indicators.
            </p>
          </div>
        </div>
      </section>
      <RecommendationList />
    </div>
  );
}

export function HistoryView() {
  const [rows, setRows] = useState<AssessmentRecord[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchAssessmentHistory()
      .then(setRows)
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Unable to load history.",
        ),
      );
  }, []);
  return (
    <div className="space-y-5 max-w-5xl">
      <section className={card}>
        <div className="flex items-center gap-3">
          <Clock3 className="text-blue-600" size={20} />
          <div>
            <h2 className="text-[20px] font-extrabold text-[#0F172A]">
              Assessment History
            </h2>
            <p className="text-[12px] text-slate-500">
              Stored complete and estimated FRIE assessments for this account.
            </p>
          </div>
        </div>
        {error && (
          <p role="alert" className="mt-4 text-red-700 text-[13px]">
            {error}
          </p>
        )}
        {rows === null ? (
          <p className="py-8 text-center text-[13px] text-slate-500">
            Loading history…
          </p>
        ) : rows.length === 0 ? (
          <p className="py-8 text-center text-[13px] text-slate-500">
            No assessments yet.
          </p>
        ) : (
          <div className="overflow-x-auto mt-5">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-slate-400 border-b">
                  <th className="py-3">Score</th>
                  <th>Reliability</th>
                  <th>Assessed</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b last:border-0 text-[13px]"
                  >
                    <td className="py-3 font-bold text-[#0F172A]">
                      {row.frie_score.toFixed(1)}
                    </td>
                    <td>{row.reliability_level}</td>
                    <td>{new Date(row.created_at).toLocaleString()}</td>
                    <td>
                      {row.assessment_state === "estimated"
                        ? "Estimated FRIE Score"
                        : "FRIE Score"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export function SettingsView({
  onNavigate,
}: {
  onNavigate: (view: View) => void;
}) {
  const [account, setAccount] = useState<AuthAccount | null>(null);
  const [latest, setLatest] = useState<AssessmentRecord | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([fetchAccount(), fetchLatestAssessment()])
      .then(([a, p]) => {
        setAccount(a);
        setLatest(p);
      })
      .catch((err) =>
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load account settings.",
        ),
      );
  }, []);
  return (
    <div className="space-y-5 max-w-4xl">
      <section className={card}>
        <div className="flex items-center gap-3">
          <Settings2 className="text-blue-600" size={20} />
          <div>
            <h2 className="text-[20px] font-extrabold text-[#0F172A]">
              Settings
            </h2>
            <p className="text-[12px] text-slate-500">
              Account information and prototype capabilities.
            </p>
          </div>
        </div>
        {error && (
          <p role="alert" className="text-red-700 text-[13px] mt-3">
            {error}
          </p>
        )}
        <div className="mt-5 grid sm:grid-cols-2 gap-4">
          <div className="rounded-lg bg-slate-50 p-4">
            <p className="text-[11px] uppercase font-bold text-slate-400">
              Account
            </p>
            <p className="mt-1 text-[14px] font-semibold text-slate-800">
              {account?.email ?? "Loading…"}
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 p-4">
            <p className="text-[11px] uppercase font-bold text-slate-400">
              Latest assessment
            </p>
            <p className="mt-1 text-[14px] font-semibold text-slate-800">
              {latest
                ? `${latest.frie_score.toFixed(1)} · ${new Date(latest.created_at).toLocaleDateString()}`
                : "Not yet calculated"}
            </p>
          </div>
        </div>
        <div className="mt-4 flex items-start gap-2 text-[12px] text-slate-500">
          <Info size={15} className="mt-0.5 shrink-0" />
          Password changes and notification preferences are not implemented in
          this prototype.
        </div>
        <button
          type="button"
          onClick={() => onNavigate("profile")}
          className="mt-4 text-[13px] font-semibold text-blue-700"
        >
          Edit profile and declarations
        </button>
      </section>
    </div>
  );
}
