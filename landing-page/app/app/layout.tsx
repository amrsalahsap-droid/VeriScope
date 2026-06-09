import { auth, signOut } from "@/auth";
import { redirect } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import {
  GitPullRequest,
  CheckCircle2,
  AlertTriangle,
  Github,
  LogOut,
  User as UserIcon,
  Building,
  Terminal,
  Home,
  Database,
  Search,
  Activity,
  Zap,
  Settings,
  ShieldAlert,
  ChevronDown,
  Sparkles,
  HelpCircle,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DeleteAccountButton } from "@/components/delete-account-button";
import { cookies } from "next/headers";
import { Toaster } from "sonner";

export const dynamic = "force-dynamic";

// Helper to fetch profile from FastAPI - completely non-blocking
// Returns null immediately during SSR to prevent fetch errors
async function fetchWorkspaceProfile(backendToken: string): Promise<any> {
  // Don't fetch during SSR - use default values
  // This prevents network errors from blocking the layout render
  return null;
}

export default async function AppShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  // Guard: Must be authenticated
  if (!session || !session.user) {
    redirect("/login");
  }

  // Fetch profile from backend, but handle failures gracefully
  let profile = null;
  try {
    if (session.backendToken) {
      profile = await fetchWorkspaceProfile(session.backendToken);
    }
  } catch {
    // Silently ignore profile fetch errors - use defaults
    profile = null;
  }

  const currentWorkspaceName = profile?.workspace?.name || "My Workspace";
  const currentWorkspaceSlug = profile?.workspace?.slug || "my-workspace";
  const currentUserRole = profile?.workspace?.role || "OWNER";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex font-sans antialiased selection:bg-white/10 selection:text-white">
      {/* 1. SIDEBAR */}
      <aside className="w-64 border-r border-zinc-900 bg-zinc-950 flex flex-col h-screen sticky top-0 shrink-0 hidden md:flex">
        {/* Workspace Switcher */}
        <div className="h-16 px-6 border-b border-zinc-900 flex items-center justify-between">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-7 h-7 rounded-lg bg-white flex items-center justify-center shrink-0 shadow-lg shadow-white/5">
              <span className="text-zinc-950 font-black text-xs">V</span>
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-semibold text-white tracking-tight truncate leading-tight">
                {currentWorkspaceName}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono truncate leading-none mt-0.5">
                veriscope.ai/{currentWorkspaceSlug}
              </span>
            </div>
          </div>
          <ChevronDown className="w-4 h-4 text-zinc-600 hover:text-zinc-400 cursor-pointer shrink-0 ml-1.5 transition-colors duration-150" />
        </div>

        {/* Sidebar Nav items */}
        <div className="flex-1 py-6 px-4 space-y-7 overflow-y-auto">
          <div className="space-y-1">
            <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-wider px-3 mb-2 select-none">
              Overview
            </div>
            <a
              href="/app"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all duration-200"
            >
              <Home className="w-4 h-4" />
              <span>Dashboard</span>
            </a>
            <a
              href="/app/repositories"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all duration-200"
            >
              <Database className="w-4 h-4" />
              <span>Repositories</span>
            </a>
          </div>

          <div className="space-y-1">
            <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-wider px-3 mb-2 select-none">
              Intelligence
            </div>
            <a
              href="/app/recommendations"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all duration-200"
            >
              <GitPullRequest className="w-4 h-4" />
              <span>Recommendations</span>
            </a>
            <a
              href="/app/fragility"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all duration-200"
            >
              <Activity className="w-4 h-4" />
              <span>Fragility Memory</span>
            </a>
            <a
              href="/app/pilot-report"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all duration-200"
            >
              <Zap className="w-4 h-4" />
              <span>Pilot Report</span>
            </a>
          </div>

          <div className="space-y-1">
            <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-wider px-3 mb-2 select-none">
              Management
            </div>
            <a
              href="/app/settings"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-900/50 transition-all duration-200"
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </a>
          </div>
        </div>

        {/* Sidebar Footer User Menu */}
        <div className="p-4 border-t border-zinc-900 bg-zinc-950">
          <div className="flex items-center justify-between p-2 rounded-xl bg-zinc-900/40 border border-zinc-900">
            <div className="flex items-center gap-2.5 min-w-0">
              {session.user.image ? (
                <img
                  src={session.user.image}
                  alt={session.user.name || "User"}
                  className="w-8 h-8 rounded-full border border-zinc-800 shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs shrink-0 font-bold border border-zinc-700 text-zinc-300">
                  {session.user.name?.[0]?.toUpperCase() || "U"}
                </div>
              )}
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-semibold text-white truncate">
                  {session.user.name}
                </span>
                <span className="text-[10px] text-zinc-500 font-medium capitalize mt-0.5">
                  {currentUserRole.toLowerCase()}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <DeleteAccountButton backendToken={session.backendToken || null} />
              <form
                action={async () => {
                  "use server";
                  await signOut({ redirectTo: "/" });
                }}
              >
                <Button
                  type="submit"
                  variant="ghost"
                  size="icon"
                  className="w-7 h-7 text-zinc-500 hover:text-white hover:bg-zinc-900/60 transition-colors duration-150"
                  title="Sign out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </Button>
              </form>
            </div>
          </div>
        </div>
      </aside>

      {/* 2. MAIN LAYOUT CONTAINER */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Topbar */}
        <header className="h-16 border-b border-zinc-900 bg-zinc-950/40 backdrop-blur-md flex items-center justify-between px-6 sm:px-8 sticky top-0 z-30">
          <div className="flex items-center gap-3.5 text-xs text-zinc-500">
            <span className="font-semibold text-zinc-400">Veriscope App</span>
            <span className="text-zinc-800 select-none">/</span>
            <span className="font-mono text-zinc-500 uppercase tracking-widest text-[10px]">
              V1.0
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/10 text-green-400 border border-green-500/20">
              <span className="w-1 h-1 rounded-full bg-green-500 animate-pulse" />
              Engine Online
            </span>
            <HelpCircle className="w-4 h-4 text-zinc-500 hover:text-zinc-300 cursor-pointer transition-colors duration-150" />
          </div>
        </header>

        {/* Content body */}
        <main className="flex-1 p-6 sm:p-8 overflow-y-auto bg-zinc-950/20">
          {children}
        </main>
      </div>
      
      {/* Toast Provider */}
      <Toaster 
        position="bottom-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#18181b',
            border: '1px solid #27272a',
            color: '#fafafa',
          },
        }}
      />
    </div>
  );
}
