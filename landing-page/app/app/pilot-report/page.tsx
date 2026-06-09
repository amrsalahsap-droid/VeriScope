import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { Zap, HelpCircle, FileText, ArrowUpRight } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function PilotReportPage() {
  const session = await auth();

  if (!session || !session.user) {
    redirect("/login");
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">
          Pilot Execution Report
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Review executive regression reduction performance, pilot duration, and cost calibration metrics
        </p>
      </div>

      <div className="bg-zinc-900/20 border border-zinc-900 rounded-2xl p-6 sm:p-8 space-y-6">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-amber-500" />
          <span className="text-sm font-semibold text-white">Q2 Pilot Benchmark</span>
        </div>
        <p className="text-xs text-zinc-400 leading-relaxed max-w-xl">
          Your Veriscope pilot has achieved a net runtime reduction of <strong className="text-zinc-200">24.5 hours</strong> across your linked team repositories, translating to roughly $1,400 in direct CI virtual infrastructure savings.
        </p>
        <button className="flex items-center gap-1.5 text-xs font-semibold text-white hover:underline">
          Download Executive PDF
          <ArrowUpRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
