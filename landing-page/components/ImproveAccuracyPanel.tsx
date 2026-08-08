"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  FileText, 
  Link, 
  Upload, 
  Play, 
  BarChart3, 
  Cog, 
  Plus, 
  ExternalLink,
  Clock,
  TrendingUp,
  AlertCircle,
  CheckCircle2
} from "lucide-react";
import { toast } from "sonner";
import BusinessRequirementsModal from "./requirements/business-requirements-modal";

interface AccuracyAction {
  id: string;
  title: string;
  description: string;
  benefit: string;
  estimatedGain: string; // percentage
  effort: string;
  icon: React.ElementType;
  available: boolean;
  priority: "high" | "medium" | "low";
  action: () => void;
  comingSoon?: boolean;
}

interface ImproveAccuracyPanelProps {
  recommendationRunId: string;
  repositoryId: string;
  pullRequestId?: string;
  missingSignals: string[];
  currentCompleteness: number;
  onActionComplete?: (actionId: string) => void;
  onRefreshRun?: () => void;
}

export function ImproveAccuracyPanel({
  recommendationRunId,
  repositoryId,
  pullRequestId,
  missingSignals,
  currentCompleteness,
  onActionComplete,
  onRefreshRun
}: ImproveAccuracyPanelProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [isPasteModalOpen, setIsPasteModalOpen] = useState(false);

  // Generate actions based on missing signals
  const generateActions = (): AccuracyAction[] => {
    const actions: AccuracyAction[] = [];

    // Manage Business Requirements - Always available
    if (missingSignals.includes("acceptance_criteria")) {
      actions.push({
        id: "paste_acceptance_criteria",
        title: "Manage Business Requirements",
        description: "Add business requirements and acceptance criteria to improve scenario precision",
        benefit: "Better scenario precision and requirement coverage",
        estimatedGain: "+12%",
        effort: "1 minute",
        icon: FileText,
        available: true,
        priority: "high",
        action: () => handlePasteAcceptanceCriteria()
      });
    }

    // Connect Jira/Azure - Coming soon if not available
    if (missingSignals.includes("work_items")) {
      actions.push({
        id: "connect_jira_azure",
        title: "Connect Jira/Azure",
        description: "Link your project management tools to automatically import requirements",
        benefit: "Automatic requirement import and traceability",
        estimatedGain: "+15%",
        effort: "5 minutes",
        icon: Link,
        available: false, // Not implemented yet
        priority: "medium",
        action: () => handleConnectJiraAzure(),
        comingSoon: true
      });
    }

    // Upload Manual Test Cases
    if (missingSignals.includes("manual_tests")) {
      actions.push({
        id: "upload_manual_tests",
        title: "Upload Manual Test Cases",
        description: "Import existing manual test cases to improve test coverage analysis",
        benefit: "Better coverage analysis and test mapping",
        estimatedGain: "+8%",
        effort: "3 minutes",
        icon: Upload,
        available: true,
        priority: "medium",
        action: () => handleUploadManualTests()
      });
    }

    // Attach Latest Test Run
    if (missingSignals.includes("test_execution")) {
      actions.push({
        id: "attach_test_run",
        title: "Attach Latest Test Run",
        description: "Connect recent test execution results for better confidence scoring",
        benefit: "Improved confidence scoring and execution insights",
        estimatedGain: "+10%",
        effort: "2 minutes",
        icon: Play,
        available: true,
        priority: "high",
        action: () => handleAttachTestRun()
      });
    }

    // Upload Updated Coverage
    if (missingSignals.includes("coverage_report")) {
      actions.push({
        id: "upload_coverage",
        title: "Upload Updated Coverage",
        description: "Add recent code coverage reports to improve recommendation accuracy",
        benefit: "Better test selection and coverage analysis",
        estimatedGain: "+7%",
        effort: "2 minutes",
        icon: BarChart3,
        available: true,
        priority: "medium",
        action: () => handleUploadCoverage()
      });
    }

    // Enable CI/CD Automation - Always coming soon
    actions.push({
      id: "enable_cicd",
      title: "Enable CI/CD Automation",
      description: "Configure automated recommendations for your CI/CD pipeline",
      benefit: "Continuous improvement and automated testing",
      estimatedGain: "+20%",
      effort: "15 minutes",
      icon: Cog,
      available: false, // Not implemented yet
      priority: "low",
      action: () => handleEnableCICD(),
      comingSoon: true
    });

    return actions;
  };

  const actions = generateActions();
  
  // Sort by priority and availability
  const sortedActions = actions.sort((a, b) => {
    // Available actions first
    if (a.available && !b.available) return -1;
    if (!a.available && b.available) return 1;
    
    // Then by priority
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    return priorityOrder[a.priority] - priorityOrder[b.priority];
  });

  const handlePasteAcceptanceCriteria = async () => {
    setIsPasteModalOpen(true);
  };

  const handleConnectJiraAzure = async () => {
    setLoading("connect_jira_azure");
    try {
      toast.info("Integration coming soon", {
        description: "Jira/Azure integration will be available in the next release"
      });
    } finally {
      setLoading(null);
    }
  };

  const handleUploadManualTests = async () => {
    setLoading("upload_manual_tests");
    try {
      // This would open file upload dialog
      toast.success("Test case upload opened", {
        description: "Select your manual test case files to import"
      });
      onActionComplete?.("upload_manual_tests");
    } catch (error) {
      toast.error("Failed to open upload", {
        description: "Please try again later."
      });
    } finally {
      setLoading(null);
    }
  };

  const handleAttachTestRun = async () => {
    setLoading("attach_test_run");
    try {
      // This would open test run selection
      toast.success("Test run selection opened", {
        description: "Select your latest test run to attach"
      });
      onActionComplete?.("attach_test_run");
    } catch (error) {
      toast.error("Failed to open test run selection", {
        description: "Please try again later."
      });
    } finally {
      setLoading(null);
    }
  };

  const handleUploadCoverage = async () => {
    setLoading("upload_coverage");
    try {
      // This would open coverage upload dialog
      toast.success("Coverage upload opened", {
        description: "Select your coverage report files to upload"
      });
      onActionComplete?.("upload_coverage");
    } catch (error) {
      toast.error("Failed to open coverage upload", {
        description: "Please try again later."
      });
    } finally {
      setLoading(null);
    }
  };

  const handleEnableCICD = async () => {
    setLoading("enable_cicd");
    try {
      toast.info("CI/CD automation coming soon", {
        description: "Automated CI/CD integration will be available in the next release"
      });
    } finally {
      setLoading(null);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high": return "text-rose-400";
      case "medium": return "text-amber-400";
      case "low": return "text-blue-400";
      default: return "text-zinc-400";
    }
  };

  const getGainColor = (gain: string) => {
    const value = parseInt(gain.replace("+", "").replace("%", ""));
    if (value >= 12) return "text-emerald-400";
    if (value >= 8) return "text-blue-400";
    return "text-zinc-400";
  };

  const getEffortColor = (effort: string) => {
    const value = parseInt(effort.split(" ")[0]);
    if (value <= 2) return "text-emerald-400";
    if (value <= 5) return "text-amber-400";
    return "text-rose-400";
  };

  if (actions.length === 0) {
    return null;
  }

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg bg-emerald-950/20 border border-emerald-800/40">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">Improve Accuracy</h3>
          <p className="text-sm text-zinc-400">Turn missing intelligence into actionable next steps</p>
        </div>
      </div>

      {/* Current Status */}
      <div className="mb-6 p-4 bg-zinc-950/40 rounded-lg border border-zinc-800/50">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-zinc-400 mb-1">Current Intelligence Completeness</p>
            <p className="text-2xl font-bold text-white">{currentCompleteness}%</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-zinc-400 mb-1">Potential Improvement</p>
            {(() => {
              const availableActions = actions.filter(a => a.available);
              if (availableActions.length === 0) {
                return <p className="text-2xl font-bold text-zinc-500">N/A</p>;
              }
              const minGain = Math.min(...availableActions.map(a => parseInt(a.estimatedGain.replace("+", "").replace("%", ""))));
              return <p className="text-2xl font-bold text-emerald-400">+{minGain}%</p>;
            })()}
          </div>
        </div>
      </div>

      {/* Action Cards */}
      <div className="space-y-3">
        {sortedActions.map((action) => {
          const Icon = action.icon;
          const isLoading = loading === action.id;
          
          return (
            <div
              key={action.id}
              className={`relative rounded-lg border p-4 transition-all ${
                action.available
                  ? "bg-zinc-950/40 border-zinc-800/50 hover:bg-zinc-950/60 hover:border-zinc-700/50 cursor-pointer"
                  : "bg-zinc-950/20 border-zinc-800/30 opacity-60"
              }`}
              onClick={action.available && !isLoading ? action.action : undefined}
            >
              {/* Priority Indicator */}
              {action.available && action.priority === "high" && (
                <div className="absolute top-2 right-2">
                  <div className="w-2 h-2 bg-rose-400 rounded-full" />
                </div>
              )}

              <div className="flex items-start gap-4">
                <div className={`p-2 rounded-lg ${
                  action.available
                    ? "bg-emerald-950/20 border border-emerald-800/40"
                    : "bg-zinc-800/40 border border-zinc-700/40"
                }`}>
                  <Icon className={`w-5 h-5 ${
                    action.available ? "text-emerald-400" : "text-zinc-500"
                  }`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="text-sm font-semibold text-white">{action.title}</h4>
                    {action.comingSoon && (
                      <span className="text-xs px-2 py-1 bg-amber-950/30 text-amber-400 border border-amber-800/40 rounded">
                        Coming soon
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400 mb-3">{action.description}</p>

                  {/* Benefits and Metrics */}
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <span className="text-zinc-500 block mb-1">Benefit</span>
                      <span className="text-zinc-300">{action.benefit}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block mb-1">Estimated Gain</span>
                      <span className={`font-semibold ${getGainColor(action.estimatedGain)}`}>
                        {action.estimatedGain}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block mb-1">Effort</span>
                      <span className={`font-semibold ${getEffortColor(action.effort)}`}>
                        {action.effort}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Action Button */}
                <div className="flex items-center gap-2">
                  {action.available ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isLoading}
                      className="bg-zinc-800 hover:bg-emerald-700 text-emerald-400 border-zinc-700"
                    >
                      {isLoading ? (
                        <div className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Plus className="w-4 h-4" />
                      )}
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled
                      className="bg-zinc-800 text-zinc-500 border-zinc-700"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>

              {/* Coming Soon Overlay */}
              {action.comingSoon && (
                <div className="absolute inset-0 bg-zinc-900/80 rounded-lg flex items-center justify-center">
                  <div className="text-center">
                    <AlertCircle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
                    <p className="text-sm font-medium text-amber-400">Coming Soon</p>
                    <p className="text-xs text-zinc-400 mt-1">Manual paste/import available</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="mt-6 pt-4 border-t border-zinc-800/50">
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span>Available actions can improve recommendation quality</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3 h-3 text-zinc-400" />
            <span>Enterprise integrations coming soon</span>
          </div>
        </div>
      </div>
      <BusinessRequirementsModal
        isOpen={isPasteModalOpen}
        onClose={() => setIsPasteModalOpen(false)}
        onSuccess={(updatedReadiness, recommendationStale) => {
          toast.success("Business Requirements Added", {
            description: "Regenerate recommendation to include requirement coverage."
          });
          onActionComplete?.("paste_acceptance_criteria");
          if (recommendationStale && onRefreshRun) {
            onRefreshRun();
          }
        }}
        repositoryId={repositoryId}
        pullRequestId={pullRequestId}
      />
    </div>
  );
}
