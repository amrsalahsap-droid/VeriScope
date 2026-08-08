import React from "react";
import { Zap, Shield, Layers } from "lucide-react";

export type ScopeModeSelectorProps = {
  value: "targeted" | "risk_based" | "full_suite";
  onChange: (mode: "targeted" | "risk_based" | "full_suite") => void;
};

export const ScopeModeSelector: React.FC<ScopeModeSelectorProps> = ({
  value,
  onChange,
}) => {
  const options = [
    {
      id: "targeted" as const,
      label: "Targeted Mode",
      description: "Only test direct impact",
      icon: Zap,
    },
    {
      id: "risk_based" as const,
      label: "Risk-Based Mode",
      description: "Expand to risk boundaries",
      icon: Shield,
    },
    {
      id: "full_suite" as const,
      label: "Full Suite",
      description: "Run complete validation",
      icon: Layers,
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onChange(opt.id)}
            className={`flex items-start gap-3 p-3.5 rounded-xl border text-left transition-all ${
              active
                ? "bg-purple-950/20 border-purple-500/50 text-purple-400 shadow-lg shadow-purple-950/20"
                : "bg-zinc-900/30 border-zinc-800/80 text-zinc-400 hover:bg-zinc-800/20 hover:border-zinc-700/80"
            }`}
          >
            <Icon className={`w-4 h-4 mt-0.5 ${active ? "text-purple-400" : "text-zinc-500"}`} />
            <div>
              <div className="text-xs font-semibold">{opt.label}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">{opt.description}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
};
export default ScopeModeSelector;
