import { auth, signOut } from "@/auth";
import { Button } from "@/components/ui/button";
import {
  GitPullRequest,
  CheckCircle2,
  AlertTriangle,
  Github,
  LogOut,
  User as UserIcon,
  ShieldAlert,
  Building,
  Terminal,
} from "lucide-react";
import Image from "next/image";

export const dynamic = "force-dynamic";

// Simple helper to fetch from FastAPI with authentication token
async function fetchFastAPIMe(backendToken: string) {
  try {
    const res = await fetch("http://localhost:8000/auth/me", {
      headers: {
        Authorization: `Bearer ${backendToken}`,
      },
      next: { revalidate: 0 }, // no-cache
    });
    if (!res.ok) {
      throw new Error(`FastAPI returned status ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error("FastAPI fetch error:", error);
    return null;
  }
}

export default async function DashboardPage() {
  const session = await auth();

  if (!session || !session.user) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6">
        <ShieldAlert className="w-12 h-12 text-red-500 mb-4 animate-bounce" />
        <h1 className="text-xl font-semibold mb-2">Access Denied</h1>
        <p className="text-sm text-zinc-500 mb-4">Please log in to continue.</p>
        <a href="/login">
          <Button>Go to Login</Button>
        </a>
      </div>
    );
  }

  // Fetch verified user + organization information from FastAPI using NextAuth shared token
  const fastapiUser = session.backendToken
    ? await fetchFastAPIMe(session.backendToken)
    : null;

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col text-zinc-100">
      {/* Dashboard Navbar */}
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center">
              <span className="text-zinc-950 font-extrabold text-sm">V</span>
            </div>
            <span className="font-semibold text-white tracking-tight">
              VERISCOPE
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              {session.user.image ? (
                <Image
                  src={session.user.image}
                  alt={session.user.name || "User Avatar"}
                  width={28}
                  height={28}
                  className="rounded-full border border-zinc-700"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center text-xs border border-zinc-700">
                  {session.user.name?.[0]?.toUpperCase() || "U"}
                </div>
              )}
              <span className="text-xs font-medium text-zinc-400 hidden sm:inline-block">
                {session.user.name || session.user.email}
              </span>
            </div>

            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/" });
              }}
            >
              <Button
                type="submit"
                variant="ghost"
                size="sm"
                className="text-zinc-400 hover:text-white border border-zinc-800 hover:bg-zinc-900 gap-1.5 h-8 px-2.5"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline-block text-xs">Logout</span>
              </Button>
            </form>
          </div>
        </div>
      </header>

      {/* Main Dashboard Experience */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full space-y-8">
        {/* Welcome Block */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-zinc-900 pb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white">
              Regression Dashboard
            </h1>
            <p className="text-sm text-zinc-400 mt-1.5">
              Active workspace:{" "}
              <span className="font-semibold text-zinc-200">
                {fastapiUser?.workspace?.name || "Initializing..."}
              </span>
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              Connected
            </span>
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid md:grid-cols-3 gap-6">
          {/* Identity & Workspace Card */}
          <div className="md:col-span-2 p-6 rounded-xl bg-zinc-900/40 border border-zinc-800 space-y-6">
            <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
              <UserIcon className="w-4 h-4 text-zinc-500" />
              Active Workspace & Identity Claims
            </h2>

            <div className="grid sm:grid-cols-2 gap-6">
              {/* FastAPI Resolved claims */}
              <div className="space-y-4">
                <div className="text-xs text-zinc-500 font-medium uppercase">
                  Resolved by FastAPI Backend
                </div>
                {fastapiUser ? (
                  <div className="space-y-3.5 bg-zinc-900/50 p-4 rounded-lg border border-zinc-800/80">
                    <div className="flex items-center gap-2.5">
                      <Building className="w-4 h-4 text-zinc-400" />
                      <div>
                        <div className="text-xs text-zinc-500">Workspace</div>
                        <div className="text-sm font-medium text-white">
                          {fastapiUser.workspace?.name}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <Terminal className="w-4 h-4 text-zinc-400" />
                      <div>
                        <div className="text-xs text-zinc-500">Workspace Slug</div>
                        <div className="text-sm font-mono text-zinc-300">
                          {fastapiUser.workspace?.slug}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5 pt-1.5 border-t border-zinc-800/60">
                      <UserIcon className="w-4 h-4 text-zinc-400" />
                      <div>
                        <div className="text-xs text-zinc-500">Workspace Role</div>
                        <div className="text-xs font-semibold px-2 py-0.5 mt-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700 inline-block">
                          {fastapiUser.workspace?.role || "MEMBER"}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-zinc-800 bg-zinc-900/20 text-xs text-amber-500 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>
                      Unable to resolve user details from FastAPI backend. Verify the backend server is running.
                    </span>
                  </div>
                )}
              </div>

              {/* NextAuth details */}
              <div className="space-y-4">
                <div className="text-xs text-zinc-500 font-medium uppercase">
                  NextAuth JWT Session (Frontend)
                </div>
                <div className="space-y-3 bg-zinc-900/50 p-4 rounded-lg border border-zinc-800/80 text-sm text-zinc-300">
                  <div>
                    <span className="text-xs text-zinc-500 block">Name</span>
                    <span className="font-medium text-white">{session.user.name}</span>
                  </div>
                  <div>
                    <span className="text-xs text-zinc-500 block">Email</span>
                    <span className="font-mono text-xs">{session.user.email}</span>
                  </div>
                  <div className="pt-2 border-t border-zinc-800/60">
                    <span className="text-xs text-zinc-500 block mb-1">Signed JWT Token</span>
                    <div className="bg-zinc-950 p-2 rounded text-[10px] font-mono break-all text-zinc-400 max-h-16 overflow-y-auto border border-zinc-800">
                      {session.backendToken}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Stats side card */}
          <div className="p-6 rounded-xl bg-zinc-900/40 border border-zinc-800 space-y-4">
            <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
              Integration Summary
            </h2>
            <div className="space-y-3.5 pt-2">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
                <span className="text-sm text-zinc-400">Database Driver</span>
                <span className="text-xs font-mono text-zinc-300">Psycopg2</span>
              </div>
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
                <span className="text-sm text-zinc-400">Authentication</span>
                <span className="text-xs font-medium text-green-400">Auth.js v5</span>
              </div>
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
                <span className="text-sm text-zinc-400">Encryption Method</span>
                <span className="text-xs font-mono text-zinc-300">HS256 (Shared Secret)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Repository Limit</span>
                <span className="text-xs font-mono text-zinc-300">Unlimited</span>
              </div>
            </div>
          </div>
        </div>

        {/* Demo operational view inside dashboard */}
        <div className="border border-zinc-800 rounded-xl bg-zinc-900/20 p-6 space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <GitPullRequest className="w-5 h-5 text-zinc-400" />
            Connected Repositories & Active Pulses
          </h2>
          <p className="text-sm text-zinc-400">
            Install the Veriscope GitHub application to begin analyzing pull requests in real time.
          </p>
          <div className="pt-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800 flex items-center justify-between group hover:border-zinc-700 transition-colors duration-200">
              <div className="flex items-center gap-3">
                <Github className="w-5 h-5 text-zinc-400" />
                <span className="text-sm font-medium">veriscope-ai/core</span>
              </div>
              <span className="text-xs text-green-400 font-medium">Active</span>
            </div>
            <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800 flex items-center justify-between group hover:border-zinc-700 transition-colors duration-200">
              <div className="flex items-center gap-3">
                <Github className="w-5 h-5 text-zinc-400" />
                <span className="text-sm font-medium">veriscope-ai/webapp</span>
              </div>
              <span className="text-xs text-green-400 font-medium">Active</span>
            </div>
            <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800 flex items-center justify-between group hover:border-zinc-700 transition-colors duration-200 cursor-pointer border-dashed hover:bg-zinc-900/80">
              <span className="text-xs font-medium text-zinc-500">+ Connect Repository</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
