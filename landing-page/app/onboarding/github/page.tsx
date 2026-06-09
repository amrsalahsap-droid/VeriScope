import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { Button } from "@/components/ui/button";
import {
  Github,
  CheckCircle2,
  Shield,
  Eye,
  GitPullRequest,
  Database,
  ArrowRight,
  Loader2,
} from "lucide-react";

export const dynamic = "force-dynamic";

// Fetch workspace GitHub installation status
async function getInstallationStatus(backendToken: string) {
  try {
    console.log('[GitHub Onboarding] Fetching installation status...');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    // Add timeout using Promise.race
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Request timeout')), 5000)
    );
    
    const fetchPromise = fetch(`${apiUrl}/github/installation/status`, {
      headers: {
        Authorization: `Bearer ${backendToken}`,
      },
      next: { revalidate: 0 },
    });
    
    const res = await Promise.race([fetchPromise, timeoutPromise]) as Response;
    
    if (!res.ok) {
      console.warn("[GitHub Onboarding] Installation status fetch failed:", res.status);
      return null;
    }
    const data = await res.json();
    console.log('[GitHub Onboarding] Installation status:', data);
    return data;
  } catch (error: any) {
    console.warn("[GitHub Onboarding] Failed to fetch installation status:", error?.message || error);
    // Return null for any error to indicate backend unavailable
    return null;
  }
}

// Fetch installed repositories
async function getInstalledRepositories(backendToken: string) {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    // Add timeout using Promise.race
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Request timeout')), 5000)
    );
    
    const fetchPromise = fetch(`${apiUrl}/github/repositories`, {
      headers: {
        Authorization: `Bearer ${backendToken}`,
      },
      next: { revalidate: 0 },
    });
    
    const res = await Promise.race([fetchPromise, timeoutPromise]) as Response;
    
    if (!res.ok) return [];
    return await res.json();
  } catch (error) {
    console.warn("Failed to fetch repositories:", error);
    return [];
  }
}

export default async function GitHubOnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; installation_id?: string }>;
}) {
  const session = await auth();
  const params = await searchParams;
  const errorCode = params?.error;

  if (!session || !session.user) {
    redirect("/login");
  }

  // If GitHub redirected here with an installation_id but no state, auto-link it
  if (params?.installation_id && session.backendToken) {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/github/installation/link`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.backendToken}`,
        },
        body: JSON.stringify({ installation_id: parseInt(params.installation_id, 10) }),
      });
      if (res.ok) {
        redirect("/onboarding/repositories");
      }
    } catch (err) {
      console.error("Auto-link from URL param failed:", err);
    }
  }

  // Fetch installation status, but handle backend failures gracefully
  let installation = null;
  let backendAvailable = false;
  if (session.backendToken) {
    try {
      const result = await getInstallationStatus(session.backendToken);
      installation = result;
      backendAvailable = result !== null;
    } catch (err: any) {
      console.error("Failed to fetch installation status:", err?.message || err);
      backendAvailable = false;
    }
  }

  // Fetch repositories, but handle backend failures gracefully
  let repositories = [];
  if (session.backendToken && backendAvailable) {
    try {
      repositories = await getInstalledRepositories(session.backendToken);
    } catch (err: any) {
      console.error("Failed to fetch repositories:", err?.message || err);
    }
  }

  const isConnected = installation && installation.status === "ACTIVE";

  return (
    <main className="min-h-screen bg-gradient-to-b from-zinc-50 via-white to-white flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-radial from-zinc-200/40 via-zinc-100/20 to-transparent rounded-full blur-3xl -z-10" />
      <div className="absolute top-40 right-0 w-[500px] h-[500px] bg-gradient-radial from-zinc-100/60 to-transparent rounded-full blur-3xl -z-10" />

      <div className="sm:mx-auto sm:w-full sm:max-w-2xl relative z-10">
        <div className="text-center">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-semibold tracking-wider bg-zinc-100 border border-zinc-200 text-zinc-600 uppercase mb-4">
            <Github className="w-3.5 h-3.5 text-zinc-500" /> Step 2 of 2
          </span>
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-900">
            Connect GitHub
          </h2>
          <p className="mt-2 text-sm text-zinc-500">
            Link your GitHub organization to enable regression intelligence on your repositories
          </p>
        </div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-2xl relative z-10 space-y-6">
        {/* Permissions Explanation Card */}
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-xl p-6">
          <h3 className="text-sm font-semibold text-zinc-900 mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-zinc-500" />
            Required Permissions
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="flex items-start gap-3">
              <Eye className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-medium text-zinc-700">Read Repository Content</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Access code, PRs, and commit history for analysis
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <GitPullRequest className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-medium text-zinc-700">Pull Request Comments</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Post regression recommendations on PRs
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Database className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-medium text-zinc-700">Actions & Checks</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Read workflow runs and test results
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-medium text-zinc-700">Webhooks</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Real-time PR and push event notifications
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Connection Status Card */}
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-xl p-6">
          {!backendAvailable ? (
            <div className="text-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center mx-auto">
                <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-900">Backend Service Unavailable</p>
                <p className="text-xs text-zinc-500 mt-1">
                  The Veriscope backend service is not running. Please start the backend server to continue.
                </p>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-left">
                <p className="text-xs font-medium text-amber-800 mb-1">To start the backend:</p>
                <code className="text-xs text-amber-700 block bg-amber-100 px-2 py-1 rounded">
                  cd veriscope && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
                </code>
              </div>
            </div>
          ) : !isConnected ? (
            <div className="text-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-zinc-100 border border-zinc-200 flex items-center justify-center mx-auto">
                <Github className="w-8 h-8 text-zinc-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-900">GitHub App Not Connected</p>
                <p className="text-xs text-zinc-500 mt-1">
                  Install the Veriscope GitHub App to begin analyzing your repositories
                </p>
              </div>

              {errorCode && (
                <div className="text-xs text-red-500 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {errorCode === "missing_state"
                    ? "GitHub redirected back without a session token. Please use the manual link below or configure the GitHub App Setup URL."
                    : `Error: ${errorCode}`}
                </div>
              )}

              <form
                action={async () => {
                  "use server";
                  const s = await auth();
                  const redirectUri = encodeURIComponent("http://localhost:3000/onboarding/github/callback");
                  const state = encodeURIComponent(s?.backendToken || "");
                  const appName = process.env.GITHUB_APP_NAME || "veriscope";
                  redirect(
                    `https://github.com/apps/${appName}/installations/new?redirect_uri=${redirectUri}&state=${state}`
                  );
                }}
              >
                <Button
                  type="submit"
                  className="w-full sm:w-auto flex items-center justify-center gap-2 bg-zinc-900 text-white hover:bg-zinc-800 font-semibold py-2.5 px-6 transition-all duration-300"
                >
                  <Github className="w-5 h-5" />
                  Install GitHub App
                </Button>
              </form>

              {/* Recovery: already installed but stuck */}
              <details className="text-left w-full">
                <summary className="text-xs text-zinc-400 cursor-pointer hover:text-zinc-600">
                  Already installed but stuck? Enter your installation ID manually
                </summary>
                <form
                  action={async (formData: FormData) => {
                    "use server";
                    const s = await auth();
                    const id = formData.get("installation_id") as string;
                    if (!id || !s?.backendToken) {
                      redirect("/onboarding/github?error=no_session");
                      return;
                    }
                    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                    const res = await fetch(`${apiUrl}/github/installation/link`, {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${s.backendToken}`,
                      },
                      body: JSON.stringify({ installation_id: parseInt(id, 10) }),
                    });
                    if (res.ok) {
                      redirect("/onboarding/repositories");
                    } else {
                      redirect("/onboarding/github?error=manual_link_failed");
                    }
                  }}
                  className="mt-3 flex gap-2"
                >
                  <input
                    name="installation_id"
                    type="number"
                    defaultValue="135363628"
                    placeholder="Installation ID (e.g. 135363628)"
                    className="flex-1 text-xs border border-zinc-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-zinc-400"
                  />
                  <Button type="submit" size="sm" variant="outline" className="text-xs">
                    Link
                  </Button>
                </form>
              </details>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-green-50 border border-green-200 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-900">GitHub Connected</p>
                  <p className="text-xs text-zinc-500">
                    {installation.account_login} • {repositories.length} repositories
                  </p>
                </div>
              </div>

              {/* Repository List */}
              {repositories.length > 0 && (
                <div className="border-t border-zinc-100 pt-4">
                  <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                    Installed Repositories
                  </p>
                  <div className="space-y-2">
                    {repositories.slice(0, 5).map((repo: any) => (
                      <div
                        key={repo.id}
                        className="flex items-center justify-between p-3 rounded-lg bg-zinc-50 border border-zinc-100"
                      >
                        <div className="flex items-center gap-2.5">
                          <Github className="w-4 h-4 text-zinc-400" />
                          <span className="text-sm text-zinc-700">{repo.full_name}</span>
                        </div>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                            repo.is_active
                              ? "bg-green-100 text-green-700 border border-green-200"
                              : "bg-zinc-100 text-zinc-500 border border-zinc-200"
                          }`}
                        >
                          {repo.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    ))}
                    {repositories.length > 5 && (
                      <p className="text-xs text-zinc-500 text-center py-2">
                        +{repositories.length - 5} more repositories
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Continue Button */}
              <form
                action={async () => {
                  "use server";
                  const cookieStore = await cookies();
                  cookieStore.set("veriscope_github_connected", "true", {
                    maxAge: 60 * 60 * 24 * 365,
                    path: "/",
                  });
                  redirect("/onboarding/repositories");
                }}
                className="pt-2"
              >
                <Button
                  type="submit"
                  className="w-full flex items-center justify-center gap-2 bg-zinc-900 text-white hover:bg-zinc-800 font-semibold py-2.5 transition-all duration-300"
                >
                  Continue to Repository Selection
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </form>
            </div>
          )}
        </div>

        {/* Info Footer */}
        <div className="text-center">
          <p className="text-[11px] text-zinc-500">
            You can modify repository access anytime from GitHub App settings
          </p>
        </div>
      </div>
    </main>
  );
}
