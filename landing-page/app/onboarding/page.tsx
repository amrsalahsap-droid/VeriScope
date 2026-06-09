import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { Button } from "@/components/ui/button";
import { Sparkles, Terminal, ArrowRight } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const session = await auth();

  // Guard: Must be authenticated
  if (!session || !session.user) {
    redirect("/login");
  }

  // Server Action to complete onboarding
  async function completeOnboarding(formData: FormData) {
    "use server";

    const workspaceName = formData.get("workspaceName") as string;
    const workspaceSlug = formData.get("workspaceSlug") as string;

    if (!workspaceName || !workspaceSlug) {
      return;
    }

    // Call our FastAPI backend to create this workspace
    try {
      const res = await fetch("http://localhost:8000/organizations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.backendToken}`,
        },
        body: JSON.stringify({
          name: workspaceName,
          slug: workspaceSlug.toLowerCase().replace(/[^a-z0-9-]/g, ""),
        }),
      });

      if (!res.ok) {
        console.error("FastAPI workspace creation failed:", await res.text());
      }
    } catch (err) {
      console.error("Error creating workspace during onboarding:", err);
    }

    // Set onboarding cookie to allow access through middleware
    const cookieStore = await cookies();
    cookieStore.set("veriscope_onboarded", "true", {
      maxAge: 60 * 60 * 24 * 365, // 1 year
      path: "/",
    });

    redirect("/app");
  }

  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Glow backgrounds */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-radial from-zinc-800/10 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.005)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.005)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10 text-center">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-semibold tracking-wider bg-zinc-900 border border-zinc-800 text-zinc-400 uppercase mb-4">
          <Sparkles className="w-3.5 h-3.5 text-zinc-500" /> Onboarding Setup
        </span>
        <h2 className="text-3xl font-semibold tracking-tight text-white">
          Name your workspace
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          Create a fresh collaboration workspace to begin tracking regressions
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-zinc-900/40 backdrop-blur-xl py-8 px-6 border border-zinc-800 shadow-2xl rounded-2xl sm:px-10">
          <form action={completeOnboarding} className="space-y-6">
            <div>
              <label htmlFor="workspaceName" className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                Workspace Name
              </label>
              <input
                type="text"
                name="workspaceName"
                id="workspaceName"
                required
                placeholder="e.g. Acme Engineering"
                className="block w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3.5 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-700 transition duration-200"
              />
            </div>

            <div>
              <label htmlFor="workspaceSlug" className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                Workspace URL Slug
              </label>
              <div className="relative rounded-lg flex shadow-sm bg-zinc-950">
                <span className="inline-flex items-center px-3.5 rounded-l-lg border border-r-0 border-zinc-800 text-sm text-zinc-500 font-mono select-none">
                  veriscope.ai/
                </span>
                <input
                  type="text"
                  name="workspaceSlug"
                  id="workspaceSlug"
                  required
                  placeholder="acme-eng"
                  className="block w-full min-w-0 rounded-none rounded-r-lg bg-zinc-950 border border-zinc-800 px-3.5 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-700 transition duration-200"
                />
              </div>
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                className="w-full flex items-center justify-center gap-2 bg-white text-zinc-950 hover:bg-zinc-100 font-semibold py-2.5 transition-all duration-300 shadow-lg shadow-white/5"
              >
                Launch Workspace
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </form>

          <div className="mt-8 border-t border-zinc-900 pt-6">
            <div className="flex items-start gap-3 text-[11px] text-zinc-500 leading-normal">
              <Terminal className="w-4 h-4 text-zinc-600 flex-shrink-0 mt-0.5" />
              <span>
                Your workspace slug forms your isolated team environment. You can invite members once inside your dashboard.
              </span>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
