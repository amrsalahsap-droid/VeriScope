"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, TrendingUp, CheckCircle, XCircle, AlertTriangle, RotateCcw, BookOpen, Plus, Minus, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface LearnedPattern {
  pattern_key: string;
  signal_type: string;
  strength: number;
  confidence: number;
  usage_count: number;
}

interface BehaviorLearningSignal {
  behavior_id: string;
  behavior_name: string;
  signal_count: number;
  last_seen_at: string;
}

interface LearningSummary {
  total_outcomes: number;
  useful_feedback_count: number;
  missing_tests_feedback_count: number;
  manually_added_tests_count: number;
  removed_tests_count: number;
  accepted_scenarios_count: number;
  escaped_defects_count: number;
  rollback_count: number;
  top_learned_patterns: LearnedPattern[];
  behaviors_with_most_signals: BehaviorLearningSignal[];
}

export default function LearningPage() {
  const params = useParams();
  const repositoryId = params.repositoryId as string;
  
  const [learningSummary, setLearningSummary] = useState<LearningSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLearningSummary = async () => {
      try {
        const res = await fetch(`/api/repositories/${repositoryId}/learning-summary`, { cache: "no-store" });
        if (res.status === 401) { window.location.href = "/login"; return; }
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { setError(data?.error || `Error ${res.status}`); return; }
        setLearningSummary(data);
      } catch (e) {
        setError("Failed to load learning summary");
      } finally {
        setLoading(false);
      }
    };

    fetchLearningSummary();
  }, [repositoryId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-zinc-800 rounded w-48" />
            <div className="h-32 bg-zinc-800 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-4">
            <p className="text-rose-300">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  const getSignalTypeLabel = (signalType: string) => {
    switch (signalType) {
      case "MANUAL_ADDITION": return "Manual Addition";
      case "MANUAL_REMOVAL": return "Manual Removal";
      case "ACCEPTED_SCENARIO": return "Accepted Scenario";
      case "DISMISSED_SCENARIO": return "Dismissed Scenario";
      case "ESCAPED_DEFECT": return "Escaped Defect";
      case "ROLLBACK": return "Rollback";
      case "EXECUTION_RESULT": return "Execution Result";
      default: return signalType;
    }
  };

  const getSignalTypeColor = (signalType: string) => {
    switch (signalType) {
      case "MANUAL_ADDITION": return "text-emerald-400";
      case "MANUAL_REMOVAL": return "text-rose-400";
      case "ACCEPTED_SCENARIO": return "text-emerald-400";
      case "DISMISSED_SCENARIO": return "text-rose-400";
      case "ESCAPED_DEFECT": return "text-amber-400";
      case "ROLLBACK": return "text-amber-400";
      case "EXECUTION_RESULT": return "text-blue-400";
      default: return "text-zinc-400";
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link href={`/repositories/${repositoryId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Repository
            </Button>
          </Link>
          <div className="flex items-center gap-2">
            <Brain className="w-6 h-6 text-emerald-400" />
            <h1 className="text-2xl font-bold">Learning Summary</h1>
          </div>
        </div>

        {learningSummary && (
          <>
            {/* Overview Stats */}
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Total Outcomes</p>
                </div>
                <p className="text-2xl font-bold text-zinc-200">{learningSummary.total_outcomes}</p>
              </div>
              
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Useful Feedback</p>
                </div>
                <p className="text-2xl font-bold text-zinc-200">{learningSummary.useful_feedback_count}</p>
              </div>
              
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Escaped Defects</p>
                </div>
                <p className="text-2xl font-bold text-zinc-200">{learningSummary.escaped_defects_count}</p>
              </div>
              
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <RotateCcw className="w-4 h-4 text-amber-400" />
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Rollbacks</p>
                </div>
                <p className="text-2xl font-bold text-zinc-200">{learningSummary.rollback_count}</p>
              </div>
            </div>

            {/* Learning Signals */}
            <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-6 mb-8">
              <h2 className="text-lg font-semibold mb-4">Learning Signals</h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="flex items-center gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Plus className="w-5 h-5 text-blue-400" />
                  <div>
                    <p className="text-xs text-zinc-500">Manually Added Tests</p>
                    <p className="text-lg font-semibold text-zinc-200">{learningSummary.manually_added_tests_count}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Minus className="w-5 h-5 text-rose-400" />
                  <div>
                    <p className="text-xs text-zinc-500">Removed Tests</p>
                    <p className="text-lg font-semibold text-zinc-200">{learningSummary.removed_tests_count}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <BookOpen className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="text-xs text-zinc-500">Accepted Scenarios</p>
                    <p className="text-lg font-semibold text-zinc-200">{learningSummary.accepted_scenarios_count}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <XCircle className="w-5 h-5 text-amber-400" />
                  <div>
                    <p className="text-xs text-zinc-500">Missing Tests Feedback</p>
                    <p className="text-lg font-semibold text-zinc-200">{learningSummary.missing_tests_feedback_count}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Top Learned Patterns */}
            {learningSummary.top_learned_patterns.length > 0 && (
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-6 mb-8">
                <h2 className="text-lg font-semibold mb-4">Top Learned Patterns</h2>
                <div className="space-y-3">
                  {learningSummary.top_learned_patterns.map((pattern, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-zinc-200 mb-1">{pattern.pattern_key}</p>
                        <div className="flex items-center gap-3 text-xs">
                          <span className={`px-2 py-0.5 rounded bg-zinc-800 ${getSignalTypeColor(pattern.signal_type)}`}>
                            {getSignalTypeLabel(pattern.signal_type)}
                          </span>
                          <span className="text-zinc-500">Strength: {pattern.strength.toFixed(2)}</span>
                          <span className="text-zinc-500">Confidence: {pattern.confidence.toFixed(2)}</span>
                        </div>
                      </div>
                      <div className="text-right ml-4">
                        <p className="text-sm font-semibold text-zinc-200">{pattern.usage_count}</p>
                        <p className="text-xs text-zinc-500">uses</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Behaviors With Most Signals */}
            {learningSummary.behaviors_with_most_signals.length > 0 && (
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-6">
                <h2 className="text-lg font-semibold mb-4">Behaviors With Most Learning Signals</h2>
                <div className="space-y-3">
                  {learningSummary.behaviors_with_most_signals.map((behavior, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-zinc-200">{behavior.behavior_name}</p>
                        <p className="text-xs text-zinc-500 mt-1">
                          Last seen: {new Date(behavior.last_seen_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="text-right ml-4">
                        <p className="text-sm font-semibold text-zinc-200">{behavior.signal_count}</p>
                        <p className="text-xs text-zinc-500">signals</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No Learning Data */}
            {learningSummary.total_outcomes === 0 && (
              <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-8 text-center">
                <Brain className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-zinc-300 mb-2">No Learning Data Yet</h3>
                <p className="text-sm text-zinc-500">
                  Veriscope hasn't captured any outcome learning for this repository yet.
                  Start using recommendations and providing feedback to enable learning.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
