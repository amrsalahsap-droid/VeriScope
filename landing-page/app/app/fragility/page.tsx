import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { Activity, AlertTriangle, Cpu } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function FragilityPage() {
  const session = await auth();

  if (!session || !session.user) {
    redirect("/login");
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">
          Fragility Memory
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Monitor code modules exhibiting fragile regression profiles, circular imports, or elevated test failures
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-6">
        <div className="bg-zinc-900/30 border border-zinc-900 rounded-xl p-5 hover:border-zinc-800 transition duration-200">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-red-500" />
            <span className="text-sm font-semibold text-white">lib/auth/dependencies</span>
          </div>
          <div className="mt-4 space-y-2 text-xs text-zinc-400">
            <div className="flex justify-between">
              <span>Fragility Index</span>
              <span className="text-red-400 font-medium font-mono">CRITICAL (8.9/10)</span>
            </div>
            <div className="flex justify-between">
              <span>Failure Frequency</span>
              <span className="text-zinc-200 font-medium">12.4% of builds</span>
            </div>
          </div>
        </div>

        <div className="bg-zinc-900/30 border border-zinc-900 rounded-xl p-5 hover:border-zinc-800 transition duration-200">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-amber-500" />
            <span className="text-sm font-semibold text-white">core/database/session</span>
          </div>
          <div className="mt-4 space-y-2 text-xs text-zinc-400">
            <div className="flex justify-between">
              <span>Fragility Index</span>
              <span className="text-amber-400 font-medium font-mono">MEDIUM (6.2/10)</span>
            </div>
            <div className="flex justify-between">
              <span>Failure Frequency</span>
              <span className="text-zinc-200 font-medium">4.1% of builds</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
