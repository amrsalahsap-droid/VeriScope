"use client";

import React, { useState, useMemo } from "react";
import type { ScenarioCoverageMatrix } from "@/lib/scenario-coverage-matrix";
import { AlertTriangle, Star, Layers, Target, ChevronDown, ChevronRight, FileText, CheckCircle2, Clock, Zap, CheckSquare, Check, X, Play, Ban, BookOpen, Users, Shield, Code } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface SuggestedScenariosProps {
  scenarios: ScenarioCoverageMatrix[];
  recommendationRunId: string;
}

interface ScenarioOutcome {
  engineer_decision: "ACCEPTED" | "DISMISSED" | "MARKED_IMPORTANT" | "NOT_DECIDED";
  execution_status: "NOT_EXECUTED" | "PASSED" | "FAILED" | "BLOCKED" | "UNKNOWN";
  converted_to_test: boolean;
}

interface ProfessionalScenario {
  title: string;
  objective: string;
  preconditions: string[];
  test_data: Record<string, any>;
  steps: string[];
  expected_results: string[];
  priority: "critical" | "high" | "medium" | "low";
  execution_layer: "api" | "ui" | "integration" | "e2e" | "unit";
  automation_candidate: boolean;
  impacted_behavior: string;
  impacted_journey: string;
  related_changed_files: string[];
  original_identifier?: string;
}

// QC Lead Scenario Language Service (simplified client-side version)
class QCLeadScenarioLanguageService {
  generateProfessionalScenario(scenario: ScenarioCoverageMatrix): ProfessionalScenario {
    const originalId = scenario.requiredScenario;
    const behavior = scenario.impactedArea || '';
    const journey = (scenario as any).journeyName || '';
    const changedFiles = (scenario as any).relatedChangedFiles || [];
    
    // Generate professional title
    const title = this.generateProfessionalTitle(originalId, behavior, journey);
    
    // Generate objective
    const objective = this.generateObjective(behavior, journey, scenario.scenarioType || '');
    
    // Generate preconditions
    const preconditions = this.generatePreconditions(scenario.testingType || '', behavior);
    
    // Generate test data
    const testData = this.generateTestData(behavior, journey, scenario.scenarioType || '');
    
    // Generate test steps
    const steps = this.generateTestSteps(behavior, journey, scenario.testingType || '');
    
    // Generate expected results
    const expectedResults = this.generateExpectedResults(behavior, scenario.scenarioType || '');
    
    // Determine priority
    const priority = this.determinePriority(scenario.priority || '');
    
    // Determine execution layer
    const executionLayer = this.determineExecutionLayer(scenario.testingType || '', changedFiles);
    
    return {
      title,
      objective,
      preconditions,
      test_data: testData,
      steps,
      expected_results: expectedResults,
      priority,
      execution_layer: executionLayer,
      automation_candidate: scenario.automationCandidate || false,
      impacted_behavior: behavior,
      impacted_journey: journey,
      related_changed_files: changedFiles,
      original_identifier: originalId
    };
  }
  
  private generateProfessionalTitle(originalId: string, behavior: string, journey: string): string {
    const combined = `${originalId} ${behavior} ${journey}`.toLowerCase();
    
    // Authentication scenarios
    if (combined.includes('auth') || combined.includes('login') || combined.includes('signin')) {
      if (combined.includes('valid') || combined.includes('success')) {
        return "Verify user authentication succeeds with valid credentials";
      } else if (combined.includes('invalid') || combined.includes('fail')) {
        return "Verify user authentication fails appropriately with invalid credentials";
      } else {
        return "Verify user authentication process handles various credential scenarios";
      }
    }
    
    // Registration scenarios
    if (combined.includes('register') || combined.includes('signup') || combined.includes('create account')) {
      return "Verify user registration completes successfully with valid required data";
    }
    
    // Password reset scenarios
    if (combined.includes('password') && combined.includes('reset')) {
      if (combined.includes('token')) {
        return "Verify password reset succeeds with a valid, unexpired token";
      } else {
        return "Verify password reset process handles various scenarios correctly";
      }
    }
    
    // Data validation scenarios
    if (combined.includes('validate') || combined.includes('validation')) {
      return `Verify ${behavior || 'input'} validation processes data correctly`;
    }
    
    // API scenarios
    if (combined.includes('api') || combined.includes('endpoint') || combined.includes('service')) {
      return `Verify ${behavior || 'API endpoint'} handles requests appropriately`;
    }
    
    // Security scenarios
    if (combined.includes('security') || combined.includes('permission') || combined.includes('authorize')) {
      return `Verify security controls prevent unauthorized access to ${behavior || 'protected resources'}`;
    }
    
    // Generic professional title
    if (originalId) {
      const readableId = originalId.replace(/_/g, ' ').replace('should', 'Verify').replace('test', '').trim();
      return `Verify ${readableId} functions correctly`;
    }
    
    return `Verify ${behavior || 'system functionality'} operates as expected`;
  }
  
  private generateObjective(behavior: string, journey: string, scenarioType: string): string {
    if (behavior.includes('auth') || journey.includes('auth')) {
      return "To ensure the authentication system properly validates user credentials and provides appropriate access based on authentication status.";
    }
    
    if (behavior.includes('register') || journey.includes('register')) {
      return "To verify that new user registration process correctly validates required information and creates user accounts successfully.";
    }
    
    if (behavior.includes('password') || journey.includes('password')) {
      return "To ensure password reset functionality securely authenticates users and allows password changes with valid tokens.";
    }
    
    if (scenarioType === 'negative') {
      return `To validate that ${behavior || 'the system'} properly handles error conditions and invalid input scenarios.`;
    }
    
    return `To ensure ${behavior || 'the system'} functions correctly and handles various input scenarios appropriately.`;
  }
  
  private generatePreconditions(testingType: string, behavior: string): string[] {
    const preconditions = [
      "System is running and accessible",
      "Database connections are established"
    ];
    
    if (behavior.includes('auth')) {
      preconditions.push("User accounts exist in the system");
      preconditions.push("Authentication service is configured");
    }
    
    if (testingType === 'API') {
      preconditions.push("API service is deployed and running");
      preconditions.push("Required API endpoints are accessible");
    }
    
    if (testingType === 'UI') {
      preconditions.push("Frontend application is loaded");
      preconditions.push("Required UI components are rendered");
    }
    
    return preconditions;
  }
  
  private generateTestData(behavior: string, journey: string, scenarioType: string): Record<string, any> {
    if (behavior.includes('auth')) {
      return {
        "valid_credentials": {
          "username": "testuser@example.com",
          "password": "ValidPassword123!"
        },
        "invalid_credentials": {
          "username": "invalid@example.com",
          "password": "WrongPassword123!"
        }
      };
    }
    
    if (behavior.includes('register')) {
      return {
        "valid_user_data": {
          "email": "newuser@example.com",
          "password": "SecurePassword123!",
          "confirmPassword": "SecurePassword123!",
          "firstName": "John",
          "lastName": "Doe"
        },
        "invalid_user_data": {
          "email": "invalid-email",
          "password": "123",
          "confirmPassword": "different"
        }
      };
    }
    
    return {
      "sample_input": "Sample test data for scenario execution",
      "boundary_values": ["minimum", "maximum", "edge_case"]
    };
  }
  
  private generateTestSteps(behavior: string, journey: string, testingType: string): string[] {
    if (behavior.includes('auth')) {
      return [
        "Navigate to the login page",
        "Enter username and password",
        "Click the login button",
        "Verify authentication response",
        "Confirm user session status"
      ];
    }
    
    if (behavior.includes('register')) {
      return [
        "Navigate to the registration page",
        "Enter all required user information",
        "Submit the registration form",
        "Verify account creation confirmation",
        "Validate user can login with new credentials"
      ];
    }
    
    return [
      "Navigate to the relevant system component",
      "Provide appropriate input data",
      "Execute the primary action",
      "Verify system response",
      "Validate expected behavior"
    ];
  }
  
  private generateExpectedResults(behavior: string, scenarioType: string): string[] {
    if (behavior.includes('auth')) {
      return [
        "Authentication status is correctly determined",
        "Appropriate access permissions are granted",
        "User session is established or denied",
        "Security audit trail is maintained"
      ];
    }
    
    if (scenarioType === 'negative') {
      return [
        "System handles errors gracefully",
        "Appropriate error messages are displayed",
        "System security is maintained",
        "No data corruption occurs"
      ];
    }
    
    return [
      "System processes input correctly",
      "Expected output is generated",
      "No errors or exceptions occur",
      "System state remains consistent"
    ];
  }
  
  private determinePriority(priority: string): "critical" | "high" | "medium" | "low" {
    if (priority === "MUST") return "critical";
    if (priority === "SHOULD") return "high";
    if (priority === "COULD") return "medium";
    return "low";
  }
  
  private determineExecutionLayer(testingType: string, changedFiles: string[]): "api" | "ui" | "integration" | "e2e" | "unit" {
    if (testingType === "API") return "api";
    if (testingType === "UI") return "ui";
    if (testingType === "Integration") return "integration";
    if (testingType === "Unit") return "unit";
    return "e2e";
  }
}

export function SuggestedMissingTestScenarios({ scenarios, recommendationRunId }: SuggestedScenariosProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [scenarioOutcomes, setScenarioOutcomes] = useState<Record<string, ScenarioOutcome>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  
  // QC Lead Scenario Language Service
  const qcLeadService = useMemo(() => new QCLeadScenarioLanguageService(), []);

  const updateScenarioDecision = async (scenarioKey: string, decision: "ACCEPTED" | "DISMISSED" | "MARKED_IMPORTANT" | "NOT_DECIDED") => {
    setLoading(prev => ({ ...prev, [scenarioKey]: true }));
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/scenarios/${scenarioKey}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engineer_decision: decision }),
      });

      if (!response.ok) throw new Error("Failed to update decision");

      setScenarioOutcomes(prev => ({
        ...prev,
        [scenarioKey]: { ...prev[scenarioKey], engineer_decision: decision }
      }));

      const decisionLabel = decision === "ACCEPTED" ? "accepted" : decision === "DISMISSED" ? "dismissed" : decision === "MARKED_IMPORTANT" ? "marked important" : "reset";
      toast.success("Scenario decision updated", { description: `Scenario ${decisionLabel}` });
    } catch (error) {
      toast.error("Failed to update decision", { description: "Please try again later." });
    } finally {
      setLoading(prev => ({ ...prev, [scenarioKey]: false }));
    }
  };

  const updateExecutionStatus = async (scenarioKey: string, status: "PASSED" | "FAILED" | "BLOCKED") => {
    setLoading(prev => ({ ...prev, [scenarioKey]: true }));
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/scenarios/${scenarioKey}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ execution_status: status }),
      });

      if (!response.ok) throw new Error("Failed to update execution status");

      setScenarioOutcomes(prev => ({
        ...prev,
        [scenarioKey]: { ...prev[scenarioKey], execution_status: status }
      }));

      toast.success("Execution status updated", { description: `Marked as ${status}` });
    } catch (error) {
      toast.error("Failed to update status", { description: "Please try again later." });
    } finally {
      setLoading(prev => ({ ...prev, [scenarioKey]: false }));
    }
  };

  // Filter only suggested scenarios (not covered)
  const suggestedScenarios = scenarios.filter(s => s.status === "suggested");

  // Generate professional scenarios
  const professionalScenarios = useMemo(() => {
    return suggestedScenarios.map(scenario => qcLeadService.generateProfessionalScenario(scenario));
  }, [suggestedScenarios, qcLeadService]);

  if (!suggestedScenarios || suggestedScenarios.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500 text-sm">
        No missing test scenarios - all areas covered
      </div>
    );
  }

  const toggleRow = (key: string) => {
    setExpandedRow(expandedRow === key ? null : key);
  };

  const automationCandidateCount = suggestedScenarios.filter(s => s.automationCandidate).length;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span className="text-zinc-400">Missing Scenarios: {suggestedScenarios.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <Zap className="w-3 h-3 text-emerald-400" />
          <span className="text-zinc-400">Automation Candidates: {automationCandidateCount}</span>
        </div>
      </div>

      {/* Scenarios List */}
      <div className="space-y-2">
        {suggestedScenarios.map((scenario, idx) => {
          const rowKey = `${idx}-${scenario.requiredScenario}`;
          const isExpanded = expandedRow === rowKey;
          const professionalScenario = professionalScenarios[idx];
          
          return (
            <React.Fragment key={idx}>
              <div 
                className="bg-zinc-900/40 border border-zinc-800/60 rounded-lg p-4 hover:bg-zinc-900/60 transition-colors cursor-pointer"
                onClick={() => toggleRow(rowKey)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                        professionalScenario.priority === "critical" ? "bg-rose-950/30 text-rose-400 border border-rose-500/20" :
                        professionalScenario.priority === "high" ? "bg-amber-950/30 text-amber-400 border border-amber-500/20" :
                        professionalScenario.priority === "medium" ? "bg-blue-950/30 text-blue-400 border border-blue-500/20" :
                        "bg-zinc-800 text-zinc-400 border border-zinc-700"
                      }`}>
                        {professionalScenario.priority === "critical" && <Star className="w-3 h-3" />}
                        {professionalScenario.priority.charAt(0).toUpperCase() + professionalScenario.priority.slice(1)}
                      </span>
                      {professionalScenario.automation_candidate && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/30 text-emerald-400 border border-emerald-500/20">
                          <Zap className="w-3 h-3" />
                          Auto
                        </span>
                      )}
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                        professionalScenario.execution_layer === "api" ? "bg-blue-950/30 text-blue-400 border border-blue-500/20" :
                        professionalScenario.execution_layer === "ui" ? "bg-purple-950/30 text-purple-400 border border-purple-500/20" :
                        professionalScenario.execution_layer === "integration" ? "bg-amber-950/30 text-amber-400 border border-amber-500/20" :
                        professionalScenario.execution_layer === "e2e" ? "bg-green-950/30 text-green-400 border border-green-500/20" :
                        "bg-zinc-800 text-zinc-400 border border-zinc-700"
                      }`}>
                        {professionalScenario.execution_layer.toUpperCase()}
                      </span>
                    </div>
                    <h3 className="text-sm font-semibold text-zinc-100 mb-1">{professionalScenario.title}</h3>
                    {professionalScenario.original_identifier && professionalScenario.original_identifier !== professionalScenario.title && (
                      <div className="flex items-center gap-2 text-[10px] text-zinc-500 mb-2">
                        <Code className="w-3 h-3" />
                        <span className="font-mono">{professionalScenario.original_identifier}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                      <div className="flex items-center gap-1">
                        <Target className="w-3 h-3" />
                        <span>{professionalScenario.impacted_behavior || 'Unknown'}</span>
                      </div>
                      {professionalScenario.impacted_journey && (
                        <div className="flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          <span>{professionalScenario.impacted_journey}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Decision Controls */}
                    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => updateScenarioDecision(rowKey, "ACCEPTED")}
                        disabled={loading[rowKey]}
                        className="bg-zinc-800 hover:bg-emerald-700 text-emerald-400 border-zinc-700"
                        title="Accept scenario"
                      >
                        <Check className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => updateScenarioDecision(rowKey, "DISMISSED")}
                        disabled={loading[rowKey]}
                        className="bg-zinc-800 hover:bg-rose-700 text-rose-400 border-zinc-700"
                        title="Dismiss scenario"
                      >
                        <X className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => updateScenarioDecision(rowKey, "MARKED_IMPORTANT")}
                        disabled={loading[rowKey]}
                        className="bg-zinc-800 hover:bg-amber-700 text-amber-400 border-zinc-700"
                        title="Mark as important"
                      >
                        <Star className="w-3 h-3" />
                      </Button>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-zinc-500 shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-zinc-500 shrink-0" />
                    )}
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-zinc-800/50 space-y-4">
                    {/* Objective & Execution Layer */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-zinc-950/20 p-3 rounded-lg border border-zinc-800/40">
                      <div>
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1">Objective</span>
                        <p className="text-xs text-zinc-300 leading-relaxed">{professionalScenario.objective}</p>
                      </div>
                      <div className="flex flex-col gap-2">
                        <div>
                          <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-0.5">Execution Layer</span>
                          <span className="inline-flex items-center gap-1.5 text-xs text-zinc-300">
                            <Layers className="w-3.5 h-3.5 text-blue-400" />
                            {professionalScenario.execution_layer.toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-0.5">Priority</span>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                            professionalScenario.priority === "critical" ? "bg-rose-950/30 text-rose-400 border border-rose-500/20" :
                            professionalScenario.priority === "high" ? "bg-amber-950/30 text-amber-400 border border-amber-500/20" :
                            professionalScenario.priority === "medium" ? "bg-blue-950/30 text-blue-400 border border-blue-500/20" :
                            "bg-zinc-800 text-zinc-400 border border-zinc-700"
                          }`}>
                            {professionalScenario.priority.charAt(0).toUpperCase() + professionalScenario.priority.slice(1)}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Preconditions */}
                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1">Preconditions</span>
                      <ul className="text-xs text-zinc-300 space-y-1 pl-1">
                        {professionalScenario.preconditions.map((prec, precIdx) => (
                          <li key={precIdx} className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 bg-zinc-600 rounded-full" />
                            {prec}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Test Data */}
                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1">Suggested Test Data</span>
                      <div className="text-xs text-zinc-300 bg-zinc-950/60 rounded px-3 py-2 border border-zinc-800/80 leading-relaxed">
                        <pre className="whitespace-pre-wrap font-mono text-xs">
                          {JSON.stringify(professionalScenario.test_data, null, 2)}
                        </pre>
                      </div>
                    </div>
                    
                    {/* Test Steps */}
                    <div>
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1">Test Steps</span>
                      <ol className="text-xs text-zinc-300 space-y-2.5 list-decimal pl-4 leading-relaxed">
                        {professionalScenario.steps.map((step, stepIdx) => (
                          <li key={stepIdx} className="pl-1">
                            {step}
                          </li>
                        ))}
                      </ol>
                    </div>
                    
                    {/* Expected Results */}
                    <div className="space-y-2 bg-zinc-950/30 p-3.5 rounded-lg border border-zinc-800/50">
                      <div>
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1">Expected Results</span>
                        <ul className="text-xs text-emerald-300/90 space-y-1.5">
                          {professionalScenario.expected_results.map((result, resultIdx) => (
                            <li key={resultIdx} className="flex items-start gap-2">
                              <CheckSquare className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                              <span>{result}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Negative/Edge Variants */}
                    {scenario.negativeEdgeVariants && scenario.negativeEdgeVariants.length > 0 && (
                      <div className="p-3 bg-amber-950/10 border border-amber-900/20 rounded-lg">
                        <span className="text-[10px] font-bold text-amber-500/80 uppercase tracking-wider block mb-1.5">Negative / Edge Scenarios to Verify</span>
                        <ul className="text-xs text-zinc-300 space-y-1">
                          {scenario.negativeEdgeVariants.map((variant, varIdx) => (
                            <li key={varIdx} className="flex items-center gap-2">
                              <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
                              <span>{variant}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Automation Recommendation */}
                    {scenario.automationRecommendation && (
                      <div className="p-3 bg-emerald-950/10 border border-emerald-900/20 rounded-lg flex items-start gap-2.5">
                        <Zap className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block mb-0.5">Automation Strategy</span>
                          <p className="text-xs text-zinc-300 leading-relaxed">{scenario.automationRecommendation}</p>
                        </div>
                      </div>
                    )}

                    {/* Manual Execution Controls */}
                    <div className="p-3 bg-zinc-950/20 border border-zinc-800/40 rounded-lg">
                      <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block mb-2">Manual Execution</span>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => updateExecutionStatus(rowKey, "PASSED")}
                          disabled={loading[rowKey]}
                          className="bg-zinc-800 hover:bg-emerald-700 text-emerald-400 border-zinc-700"
                        >
                          <CheckCircle2 className="w-3 h-3 mr-1.5" />
                          Passed
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => updateExecutionStatus(rowKey, "FAILED")}
                          disabled={loading[rowKey]}
                          className="bg-zinc-800 hover:bg-rose-700 text-rose-400 border-zinc-700"
                        >
                          <AlertTriangle className="w-3 h-3 mr-1.5" />
                          Failed
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => updateExecutionStatus(rowKey, "BLOCKED")}
                          disabled={loading[rowKey]}
                          className="bg-zinc-800 hover:bg-amber-700 text-amber-400 border-zinc-700"
                        >
                          <Ban className="w-3 h-3 mr-1.5" />
                          Blocked
                        </Button>
                      </div>
                      {/* Execution Status Display */}
                      {scenarioOutcomes[rowKey]?.execution_status && scenarioOutcomes[rowKey].execution_status !== "NOT_EXECUTED" && (
                        <div className="mt-2 pt-2 border-t border-zinc-800/50">
                          <span className={`text-[10px] font-medium ${
                            scenarioOutcomes[rowKey].execution_status === "PASSED" ? "text-emerald-400" :
                            scenarioOutcomes[rowKey].execution_status === "FAILED" ? "text-rose-400" :
                            "text-amber-400"
                          }`}>
                            Status: {scenarioOutcomes[rowKey].execution_status}
                          </span>
                        </div>
                      )}
                    </div>
                    
                    {/* Related Changed Files */}
                    {scenario.relatedChangedFiles && scenario.relatedChangedFiles.length > 0 && (
                      <div>
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1.5">Triggered by Changes In</span>
                        <div className="flex flex-wrap gap-1.5">
                          {scenario.relatedChangedFiles.slice(0, 5).map((file, fileIdx) => (
                            <span key={fileIdx} className="text-[10px] bg-zinc-800/80 text-zinc-400 px-2 py-0.5 rounded border border-zinc-700/60 truncate max-w-[250px] font-mono">
                              {file}
                            </span>
                          ))}
                          {scenario.relatedChangedFiles.length > 5 && (
                            <span className="text-[10px] text-zinc-500 font-medium">+{scenario.relatedChangedFiles.length - 5} more</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-zinc-500 pt-2 border-t border-zinc-800/50 flex-wrap">
        <div className="flex items-center gap-1">
          <Star className="w-3 h-3 text-rose-400" />
          <span>MUST: Critical scenarios</span>
        </div>
        <div className="flex items-center gap-1">
          <Zap className="w-3 h-3 text-emerald-400" />
          <span>Auto: Suitable for automation</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-zinc-400">Click row to expand details</span>
        </div>
      </div>
    </div>
  );
}
