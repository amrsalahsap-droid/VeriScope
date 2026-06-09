import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { Settings, Shield, User as UserIcon, Building } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const session = await auth();

  if (!session || !session.user) {
    redirect("/login");
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">
          Workspace Settings
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Configure security settings, default reduction policies, and team memberships
        </p>
      </div>

      <div className="bg-zinc-900/10 border border-zinc-900 rounded-xl p-6 space-y-6">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <Shield className="w-4 h-4 text-zinc-500" />
          Reduction Governance
        </h2>
        <div className="space-y-4 text-sm text-zinc-300">
          <div className="flex items-center justify-between pb-3.5 border-b border-zinc-900">
            <div>
              <p className="font-semibold text-white">Default Reduction Target</p>
              <p className="text-xs text-zinc-500">Safely target test suite optimization ratio</p>
            </div>
            <span className="font-mono text-xs text-zinc-400">30% - 50%</span>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-white">Verification Engine</p>
              <p className="text-xs text-zinc-500">Enforce HS256 JWT signature verification across microservices</p>
            </div>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20">
              Enabled
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
