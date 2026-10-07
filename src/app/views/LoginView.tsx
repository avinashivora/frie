import { useState } from "react";
import { Activity, AlertCircle, Shield, Zap } from "lucide-react";
import svgPaths from "@/imports/RightSplit/svg-qcu94pqgtn";
import { FrieApiError, loginUser, registerUser, type AuthSession } from "../../services/api";

export default function LoginView({ onLogin }: { onLogin: (session: AuthSession, isNewRegistration?: boolean) => void }) {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [mode, setMode]         = useState<"signin" | "register">("signin");
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState("");

  function switchMode(next: "signin" | "register") {
    setMode(next);
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      const session = mode === "register"
        ? await registerUser(email, password)
        : await loginUser(email, password);
      onLogin(session, mode === "register");
    } catch (err) {
      setError(err instanceof FrieApiError && err.message ? err.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#F8FAFC]">
      {/* Left branding panel */}
      <div className="hidden lg:flex flex-col justify-between w-[460px] shrink-0 bg-[#0F172A] p-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-72 h-72 bg-blue-500/10 rounded-full -translate-y-1/2 translate-x-1/3" />
        <div className="absolute bottom-0 left-0 w-56 h-56 bg-blue-400/8 rounded-full translate-y-1/2 -translate-x-1/3" />

        {/* Logo */}
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-[#3B82F6] rounded-xl flex items-center justify-center">
              <Activity size={22} className="text-white" />
            </div>
            <span className="text-white text-2xl font-extrabold tracking-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
              FRIE
            </span>
          </div>
          <p className="text-slate-400 text-[13px] ml-0.5">Financial Reliability Intelligence Engine</p>
        </div>

        {/* Main copy */}
        <div className="relative space-y-8">
          <div>
            <h2 className="text-white text-[30px] font-extrabold leading-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
              Know your financial<br />reliability score.
            </h2>
            <p className="text-slate-400 text-[14px] mt-3 leading-relaxed">
              A prototype assessment of your financial profile and documents, combined into a single reliability score.
            </p>
          </div>

          <div className="space-y-4">
            {[
              { icon: Zap,      title: "FRIE Score",         desc: "Composite reliability index from 0–100" },
              { icon: Shield,   title: "Your Own Data",      desc: "Scores computed from information you provide" },
              { icon: Activity, title: "Financial Assessment", desc: "A score based on the information you provide" },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center shrink-0 mt-0.5">
                  <Icon size={15} className="text-blue-400" />
                </div>
                <div>
                  <p className="text-white text-[13px] font-semibold">{title}</p>
                  <p className="text-slate-500 text-[12px] mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-4 pt-5 border-t border-slate-800">
            {[{ val: "FRIE", lbl: "Financial Reliability" }, { val: "Demo", lbl: "Prototype Portal" }, { val: "Individual", lbl: "For Individuals" }].map(({ val, lbl }) => (
              <div key={lbl} className="text-center">
                <p className="text-white text-[18px] font-extrabold" style={{ fontFamily: "Outfit, sans-serif" }}>{val}</p>
                <p className="text-slate-500 text-[11px]">{lbl}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-slate-700 text-[11px] relative">FRIE prototype. For demonstration purposes only.</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-8 lg:p-16 overflow-y-auto">
        <form onSubmit={handleSubmit} className="w-full max-w-[400px] flex flex-col gap-6 sm:gap-8">
          {/* Header */}
          <div className="flex flex-col gap-3">
            <p className="font-extrabold text-[#0F172A] text-[28px] sm:text-[32px] leading-tight" style={{ fontFamily: "Outfit, sans-serif" }}>
              {mode === "register" ? "Create Account" : "Welcome Back"}
            </p>
            <p className="text-[#334155] text-[14px]" style={{ fontFamily: "Geist, Inter, sans-serif" }}>
              {mode === "register"
                ? "Register to start your financial diagnostic journey"
                : "Sign in to your financial diagnostic portal"}
            </p>
          </div>

          {/* Fields */}
          <div className="flex flex-col gap-5">
            {/* Email */}
            <div className="flex flex-col gap-2">
              <label className="font-semibold text-[#0F172A] text-[13px]" style={{ fontFamily: "Geist, Inter, sans-serif" }}>
                Email Address
              </label>
              <div className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-[8px] flex items-center gap-2.5 px-3 py-3 focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-50 transition-all">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
                  <path d={svgPaths.p10d0c00} stroke="#94A3B8" strokeLinecap="round" strokeWidth="2" />
                </svg>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="flex-1 bg-transparent text-[14px] text-[#334155] placeholder:text-[#94A3B8] outline-none"
                  style={{ fontFamily: "Geist, Inter, sans-serif" }}
                  required
                />
              </div>
            </div>

            {/* Password */}
            <div className="flex flex-col gap-2">
              <label className="font-semibold text-[#0F172A] text-[13px]" style={{ fontFamily: "Geist, Inter, sans-serif" }}>
                {mode === "register" ? "Choose a Password (min. 8 characters)" : "Security Password"}
              </label>
              <div className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-[8px] flex items-center gap-2.5 px-3 py-3 focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-50 transition-all">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
                  <path d={svgPaths.p241025a0} stroke="#94A3B8" strokeLinecap="round" strokeWidth="2" />
                </svg>
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="flex-1 bg-transparent text-[14px] text-[#334155] placeholder:text-[#94A3B8] outline-none"
                  style={{ fontFamily: "Geist, Inter, sans-serif" }}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="font-bold text-[#3B82F6] text-[12px] hover:text-blue-700 transition-colors shrink-0"
                  style={{ fontFamily: "Geist, Inter, sans-serif" }}
                >
                  {showPw ? "Hide" : "Show"}
                </button>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5">
              <AlertCircle size={14} className="text-red-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-red-600 text-[13px]">{error}</p>
                <p className="text-red-400 text-[11px] mt-1">Use a valid email and at least 8 characters.</p>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col gap-4">
            <button
              type="submit"
              disabled={busy}
              className="bg-[#0F172A] hover:bg-slate-800 disabled:opacity-60 text-white font-semibold text-[14px] py-3 px-6 rounded-[8px] transition-colors w-full"
              style={{ fontFamily: "Geist, Inter, sans-serif" }}
            >
              {busy ? (mode === "register" ? "Creating account..." : "Signing in...") : (mode === "register" ? "Create Account" : "Sign In Securely")}
            </button>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center justify-center gap-1 text-[13px]">
            <span className="text-[#334155]" style={{ fontFamily: "Geist, Inter, sans-serif" }}>
              {mode === "register" ? "Already have an account?" : "New to FRIE?"}
            </span>
            <button
              type="button"
              onClick={() => switchMode(mode === "register" ? "signin" : "register")}
              className="font-bold text-[#3B82F6] hover:text-blue-700 transition-colors"
              style={{ fontFamily: "Geist, Inter, sans-serif" }}
            >
              {mode === "register" ? "Sign in" : "Register"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
