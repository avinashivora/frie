import { useState, useEffect } from "react";
import {
  Activity, FileText, LayoutDashboard, LogOut, Star, TrendingUp, User, Users, Clock3, Lightbulb, Settings2,
} from "lucide-react";
import { clearSession, fetchAccount, loadSession, saveSession, type AuthSession } from "../services/api";
import LoginView from "./views/LoginView";
import DashboardView from "./views/DashboardView";
import DocumentsView from "./views/DocumentsView";
import ProfileView from "./views/ProfileView";
import AnalysisView from "./views/AnalysisView";
import { HistoryView, RecommendationsView, ScoreReportView, SettingsView } from "./views/PortfolioViews";

// ═══════════════════════════════════════════════════════════════
// TYPES + NAVIGATION (Individual-only Working Demo)
// ═══════════════════════════════════════════════════════════════

export type View = "dashboard" | "analysis" | "documents" | "profile" | "score" | "recommendations" | "history" | "settings";
type OnboardingStep = "profile" | "financial_data" | "review" | "score";

type NavItem = { icon: React.ElementType; label: string; view: View };

const NAV_ITEMS: NavItem[] = [
  { icon: LayoutDashboard, label: "Dashboard",          view: "dashboard" },
  { icon: TrendingUp,      label: "Financial Analysis", view: "analysis" },
  { icon: Star,            label: "FRIE Score & Report", view: "score" },
  { icon: Lightbulb,       label: "Recommendations",     view: "recommendations" },
  { icon: Clock3,          label: "History",             view: "history" },
  { icon: Settings2,       label: "Settings",            view: "settings" },
  { icon: FileText,        label: "Documents",          view: "documents" },
  { icon: User,            label: "Profile",            view: "profile" },
];

const VIEW_TITLES: Record<View, string> = {
  dashboard: "Dashboard",
  analysis: "Financial Analysis",
  score: "FRIE Score & Report",
  recommendations: "Recommendations",
  history: "Assessment History",
  settings: "Settings",
  documents: "Financial Documents",
  profile: "My Profile",
};

// ═══════════════════════════════════════════════════════════════
// SIDEBAR + MOBILE NAV
// ═══════════════════════════════════════════════════════════════

function NavButtons({ view, onNavigate, vertical }: {
  view: View; onNavigate: (v: View) => void; vertical: boolean;
}) {
  return (
    <>
      {NAV_ITEMS.map(item => {
        const active = view === item.view;
        return (
          <button
            key={item.view}
            onClick={() => onNavigate(item.view)}
            className={`${vertical ? "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left mb-0.5" : "flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap"} text-[13px] font-semibold transition-all ${
              active ? "bg-[#0F172A] text-white" : "text-slate-500 hover:bg-slate-50 hover:text-[#0F172A]"
            }`}
          >
            <item.icon size={15} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </>
  );
}

function Sidebar({ view, onNavigate, onLogout, userName }: {
  view: View; onNavigate: (v: View) => void; onLogout: () => void; userName: string;
}) {
  return (
    <div className="hidden lg:flex w-[224px] shrink-0 bg-white border-r border-[#F1F5F9] flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-[#F1F5F9]">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 bg-[#0F172A] rounded-xl flex items-center justify-center">
            <Activity size={18} className="text-white" />
          </div>
          <div>
            <p className="text-[#0F172A] font-extrabold text-[18px] leading-none" style={{ fontFamily: "Outfit, sans-serif" }}>FRIE</p>
            <p className="text-[10px] font-semibold leading-none mt-0.5 text-blue-400">Individual Portal</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 overflow-y-auto">
        <p className="px-3 mb-2 text-[10px] font-bold text-slate-300 uppercase tracking-widest">Main Menu</p>
        <NavButtons view={view} onNavigate={onNavigate} vertical />
      </nav>

      {/* User + logout */}
      <div className="px-3 py-3 border-t border-[#F1F5F9]">
        <div className="flex items-center gap-2.5 px-3 py-2 mb-1">
          <div className="w-8 h-8 rounded-full bg-[#0F172A] flex items-center justify-center text-white text-[12px] font-bold shrink-0">
            {userName.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[12px] font-semibold text-[#0F172A] truncate">{userName}</p>
            <p className="text-[10px] text-slate-400 truncate">Individual Portal</p>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-red-500 hover:bg-red-50 transition-all"
        >
          <LogOut size={15} />
          <span className="text-[13px] font-semibold">Logout</span>
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// APP LAYOUT
// ═══════════════════════════════════════════════════════════════

function AppLayout({ view, onNavigate, onLogout, userName, children }: {
  view: View; onNavigate: (v: View) => void; onLogout: () => void;
  userName: string; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col lg:flex-row min-h-screen lg:h-screen bg-[#F8FAFC] lg:overflow-hidden">
      <Sidebar view={view} onNavigate={onNavigate} onLogout={onLogout} userName={userName} />
      {/* Mobile top bar */}
      <div className="lg:hidden bg-white border-b border-[#F1F5F9] px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
        <div className="w-8 h-8 bg-[#0F172A] rounded-lg flex items-center justify-center shrink-0">
          <Activity size={15} className="text-white" />
        </div>
        <p className="text-[#0F172A] font-extrabold text-[16px]" style={{ fontFamily: "Outfit, sans-serif" }}>FRIE</p>
        <div className="flex-1" />
        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 text-red-500 text-[12px] font-semibold px-2 py-1.5"
          aria-label="Logout"
        >
          <LogOut size={15} />
        </button>
      </div>
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header */}
        <div className="bg-white border-b border-[#F1F5F9] px-4 md:px-8 py-4 flex items-center justify-between shrink-0">
          <div className="min-w-0">
            <h1 className="text-[16px] md:text-[18px] font-extrabold text-[#0F172A] truncate" style={{ fontFamily: "Outfit, sans-serif" }}>
              {VIEW_TITLES[view] || "Dashboard"}
            </h1>
            <p className="text-[11px] text-slate-400 hidden sm:block">Financial Reliability Intelligence Engine</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-[#0F172A] flex items-center justify-center text-white text-[13px] font-bold shrink-0">
              {userName.charAt(0).toUpperCase()}
            </div>
          </div>
        </div>
        {/* Mobile nav */}
        <div className="lg:hidden bg-white border-b border-[#F1F5F9] px-3 py-2 flex gap-1 overflow-x-auto shrink-0">
          <NavButtons view={view} onNavigate={onNavigate} vertical={false} />
        </div>
        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════

export default function App() {
  const [session,   setSession]   = useState<AuthSession | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [view,      setView]      = useState<View>("dashboard");
  const [onboarding, setOnboarding] = useState<OnboardingStep | null>(null);

  function persistOnboarding(userId: number, step: OnboardingStep | null) {
    const key = `frie_onboarding_${userId}`;
    if (step) localStorage.setItem(key, step); else localStorage.removeItem(key);
    setOnboarding(step);
  }

  useEffect(() => {
    let live = true;
    const stored = loadSession();
    if (!stored) {
      setRestoring(false);
      return;
    }
    saveSession(stored);
    fetchAccount()
      .then(account => {
        if (!live) return;
        setSession({ token: stored.token, id: account.id, email: account.email });
        const savedStep = localStorage.getItem(`frie_onboarding_${account.id}`) as OnboardingStep | null;
        if (savedStep === "profile" || savedStep === "financial_data" || savedStep === "review" || savedStep === "score") {
          setOnboarding(savedStep);
          setView(savedStep === "profile" ? "profile" : savedStep === "financial_data" ? "documents" : savedStep === "score" ? "score" : "dashboard");
        }
        setRestoring(false);
      })
      .catch(() => {
        if (!live) return;
        clearSession();
        setRestoring(false);
      });
    return () => { live = false; };
  }, []);

  function handleLogin(next: AuthSession, isNewRegistration = false) {
    saveSession(next);
    setSession(next);
    if (isNewRegistration) {
      persistOnboarding(next.id, "profile");
      setView("profile");
    } else {
      setView("dashboard");
    }
  }
  function handleLogout() {
    clearSession();
    setSession(null);
    setView("dashboard");
    setOnboarding(null);
  }
  function navigate(v: View) {
    setView(v);
    if (session && onboarding) {
      const step = v === "profile" ? "profile" : v === "documents" ? "financial_data" : v === "score" ? "score" : "review";
      persistOnboarding(session.id, step);
    }
  }

  useEffect(() => {
    const complete = () => { if (session) persistOnboarding(session.id, null); };
    window.addEventListener("frie:assessment-created", complete);
    return () => window.removeEventListener("frie:assessment-created", complete);
  }, [session]);

  if (restoring) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC]">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-[#0F172A] border-t-transparent rounded-full animate-spin" />
          <p className="text-[13px] font-semibold text-slate-600">Restoring session...</p>
        </div>
      </div>
    );
  }
  if (!session) return <LoginView onLogin={handleLogin} />;

  const userName = session.email.split("@")[0] || "FRIE User";

  function renderContent(): React.ReactNode {
    if (!session) return null;
    switch (view) {
      case "dashboard":
        return <DashboardView onNavigate={navigate} />;
      case "analysis":
        return <AnalysisView onNavigate={navigate} />;
      case "documents":
        return <DocumentsView onContinue={() => navigate("dashboard")} />;
      case "profile":
        return <ProfileView onNavigate={navigate} />;
      case "score": return <ScoreReportView onCompleteSource={source => navigate(source === "profile" ? "profile" : "documents")} />;
      case "recommendations": return <RecommendationsView />;
      case "history": return <HistoryView />;
      case "settings": return <SettingsView onNavigate={navigate} />;
      default:
        return null;
    }
  }

  return (
    <AppLayout
      view={view}
      onNavigate={navigate}
      onLogout={handleLogout}
      userName={userName}
    >
      {onboarding && (
        <div className="mb-5 bg-white border border-[#E2E8F0] rounded-xl p-4">
          <div className="flex items-center gap-2 sm:gap-4 text-[12px] font-semibold">
            {([ ["profile", "1 · Profile"], ["financial_data", "2 · Financial Information"], ["review", "3 · Review"], ["score", "4 · FRIE Score"] ] as [OnboardingStep, string][]).map(([step, label]) => {
              const current = onboarding === step;
              return <div key={step} className={`flex-1 border-b-2 pb-2 ${current ? "border-blue-600 text-blue-700" : "border-slate-100 text-slate-400"}`}><span>{label}</span></div>;
            })}
          </div>
        </div>
      )}
      {renderContent()}
    </AppLayout>
  );
}
