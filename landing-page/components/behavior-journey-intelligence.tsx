"use client";

import { AlertTriangle, CheckCircle2, Layers, Users, FileText } from "lucide-react";

// Inline Badge component to avoid shadcn dependency
function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${className}`}>
      {children}
    </span>
  );
}

interface BehaviorImpact {
  behavior_id: string;
  behavior_name: string;
  impact_type: string; // DIRECT | INDIRECT
  impact_level: string; // CRITICAL, HIGH, MEDIUM, LOW
  behavior_confidence: string;
  behavior_risk_level: string;
  impacted_files: string[];
}

interface JourneyImpact {
  journey_id: string;
  journey_name: string;
  impact_level: string;
  risk: string;
  affected_behaviors: string[];
  evidence: Array<{ type: string; file_path?: string; behavior_name?: string; confidence: string }>;
}

interface BehaviorJourneyIntelligenceProps {
  behaviorImpact: {
    impacted_behaviors: BehaviorImpact[];
    impacted_journeys: JourneyImpact[];
    confidence: string;
  } | null;
}

export function BehaviorJourneyIntelligence({ behaviorImpact }: BehaviorJourneyIntelligenceProps) {
  if (!behaviorImpact) {
    return null;
  }

  const { impacted_behaviors, impacted_journeys, confidence } = behaviorImpact;

  const impactLevelColors: Record<string, string> = {
    CRITICAL: "bg-rose-950/20 text-rose-400 border-rose-800/30",
    HIGH: "bg-orange-950/20 text-orange-400 border-orange-800/30",
    MEDIUM: "bg-amber-950/20 text-amber-400 border-amber-800/30",
    LOW: "bg-zinc-800 text-zinc-400 border-zinc-700",
  };

  const impactTypeColors: Record<string, string> = {
    DIRECT: "bg-emerald-950/20 text-emerald-400 border-emerald-800/30",
    INDIRECT: "bg-sky-950/20 text-sky-400 border-sky-800/30",
  };

  const confidenceColors: Record<string, string> = {
    HIGH: "text-emerald-400",
    MODERATE: "text-amber-400",
    LOW: "text-rose-400",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
            <Layers className="w-5 h-5 text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Behavior & Journey Intelligence</h3>
            <p className="text-xs text-zinc-400">
              Analysis confidence: <span className={confidenceColors[confidence] || "text-zinc-400"}>{confidence}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Impacted Behaviors */}
      {impacted_behaviors.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Impacted Behaviors ({impacted_behaviors.length})
          </h4>
          <div className="space-y-2">
            {impacted_behaviors.map((behavior) => (
              <div
                key={behavior.behavior_id}
                className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-medium text-white truncate">
                        {behavior.behavior_name}
                      </span>
                      <Badge className={`text-[10px] px-1.5 py-0.5 ${impactTypeColors[behavior.impact_type]}`}>
                        {behavior.impact_type}
                      </Badge>
                      <Badge className={`text-[10px] px-1.5 py-0.5 ${impactLevelColors[behavior.impact_level]}`}>
                        {behavior.impact_level}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-zinc-500">
                      <span>Risk: {behavior.behavior_risk_level}</span>
                      <span>Confidence: {behavior.behavior_confidence}</span>
                    </div>
                  </div>
                </div>
                {behavior.impacted_files.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-zinc-800">
                    <p className="text-xs text-zinc-500 mb-1">Changed files:</p>
                    <div className="flex flex-wrap gap-1">
                      {behavior.impacted_files.slice(0, 3).map((file, idx) => (
                        <code key={idx} className="text-[10px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded">
                          {file.split("/").pop()}
                        </code>
                      ))}
                      {behavior.impacted_files.length > 3 && (
                        <span className="text-[10px] text-zinc-500">+{behavior.impacted_files.length - 3} more</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Impacted Journeys */}
      {impacted_journeys.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <Users className="w-3.5 h-3.5" />
            Impacted Journeys ({impacted_journeys.length})
          </h4>
          <div className="space-y-2">
            {impacted_journeys.map((journey) => (
              <div
                key={journey.journey_id}
                className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-medium text-white truncate">
                        {journey.journey_name}
                      </span>
                      <Badge className={`text-[10px] px-1.5 py-0.5 ${impactLevelColors[journey.impact_level]}`}>
                        {journey.impact_level}
                      </Badge>
                      <Badge className="text-[10px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400">
                        Risk: {journey.risk}
                      </Badge>
                    </div>
                    <div className="text-xs text-zinc-500">
                      {journey.affected_behaviors.length} affected behavior{journey.affected_behaviors.length !== 1 ? "s" : ""}
                    </div>
                  </div>
                </div>
                {journey.evidence.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-zinc-800">
                    <p className="text-xs text-zinc-500 mb-1">Evidence:</p>
                    <div className="space-y-1">
                      {journey.evidence.slice(0, 2).map((ev, idx) => (
                        <div key={idx} className="text-[10px] text-zinc-400">
                          • {ev.type} {ev.behavior_name && `(${ev.behavior_name})`}
                        </div>
                      ))}
                      {journey.evidence.length > 2 && (
                        <span className="text-[10px] text-zinc-500">+{journey.evidence.length - 2} more</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {impacted_behaviors.length === 0 && impacted_journeys.length === 0 && (
        <div className="p-4 rounded-lg bg-zinc-900/30 border border-zinc-800 text-center">
          <CheckCircle2 className="w-5 h-5 text-zinc-500 mx-auto mb-2" />
          <p className="text-xs text-zinc-500">No behaviors or journeys detected as impacted</p>
        </div>
      )}
    </div>
  );
}
