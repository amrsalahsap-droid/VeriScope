"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, CheckCircle2, XCircle, Clock, AlertTriangle, Play, SkipForward, Ban, GitPullRequest, GitBranch, Layers, Brain, Globe, Target, FileText, Shield, Zap, History, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";

interface ScopeItem {
  id: string;
  item_type: string;
  tier: string;
  priority: string;
  selection_reason: string;
  evidence_summary: any;
  execution_status: string;
  coverage_status: string;
  is_excluded: boolean;
  has_overrides: boolean;
  override_history: Array<{
    id: string;
    override_type: string;
    original_value: any;
    new_value: any;
    reason: string;
    overridden_by: string;
    overridden_at: string;
  }>;
  test_case?: {
    id: string;
    stable_identity: string;
    test_name: string;
    suite_name: string;
  };
  external_test_case?: {
    id: string;
    title: string;
    provider: string;
    external_key: string;
  };
  suggested_scenario?: {
    id: string;
    title: string;
    impacted_area: string;
    testing_type: string;
  };
  behavior?: {
    id: string;
    name: string;
    risk_level: string;
  };
  journey?: {
    id: string;
    name: string;
    risk_level: string;
  };
}

interface SuiteData {
  id: string;
  repository_id: string;
  release_id: string | null;
  pull_request_id: string | null;
  recommendation_run_id: string | null;
  name: string;
  description: string;
  suite_type: string;
  status: string;
  confidence_level: string;
  scope_score: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  scope_items_count: number;
}

interface ScopeData {
  suite_id: string;
  total_items: number;
  grouped_by_tier: {
    MUST_RUN: ScopeItem[];
    SHOULD_RUN: ScopeItem[];
    OPTIONAL: ScopeItem[];
    EXCLUDED: ScopeItem[];
  };
  all_items: ScopeItem[];
}

export default function RegressionSuitePage() {
  const params = useParams();
  const router = useRouter();
  const suiteId = params.suiteId as string;

  const [suite, setSuite] = useState<SuiteData | null>(null);
  const [scope, setScope] = useState<ScopeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overrideDialog, setOverrideDialog] = useState<{
    open: boolean;
    itemId: string | null;
    action: string;
    currentValue: string;
  }>({
    open: false,
    itemId: null,
    action: "",
    currentValue: "",
  });
  const [overrideReason, setOverrideReason] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [expandedOverrideItems, setExpandedOverrideItems] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadSuiteData();
  }, [suiteId]);

  const loadSuiteData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load suite details
      const suiteRes = await fetch(`/api/regression-suites/${suiteId}`);
      if (!suiteRes.ok) throw new Error("Failed to load suite");
      const suiteData: SuiteData = await suiteRes.json();
      setSuite(suiteData);

      // Load scope items
      const scopeRes = await fetch(`/api/regression-suites/${suiteId}/scope`);
      if (!scopeRes.ok) throw new Error("Failed to load scope");
      const scopeData: ScopeData = await scopeRes.json();
      setScope(scopeData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const getExecutionIcon = (status: string) => {
    switch (status) {
      case "PASSED":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "FAILED":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "SKIPPED":
        return <SkipForward className="h-4 w-4 text-yellow-500" />;
      case "BLOCKED":
        return <Ban className="h-4 w-4 text-red-600" />;
      case "MANUAL_PENDING":
        return <Clock className="h-4 w-4 text-orange-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getTierColor = (tier: string) => {
    switch (tier) {
      case "MUST_RUN":
        return "bg-red-100 text-red-800 border-red-200";
      case "SHOULD_RUN":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "OPTIONAL":
        return "bg-gray-100 text-gray-800 border-gray-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "CRITICAL":
        return "bg-red-500 text-white";
      case "HIGH":
        return "bg-orange-500 text-white";
      case "MEDIUM":
        return "bg-blue-500 text-white";
      case "LOW":
        return "bg-gray-500 text-white";
      default:
        return "bg-gray-500 text-white";
    }
  };

  const handleUpdateTier = async (itemId: string, newTier: string, reason: string) => {
    try {
      setIsUpdating(true);
      const res = await fetch(`/api/regression-suites/${suiteId}/scope/${itemId}?tier=${newTier}&reason=${encodeURIComponent(reason)}`, {
        method: "PATCH",
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update tier");
      }
      toast.success("Tier updated");
      await loadSuiteData();
    } catch (err) {
      toast.error("Failed to update tier", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleExclude = async (itemId: string, isExcluded: boolean, reason: string) => {
    try {
      setIsUpdating(true);
      const res = await fetch(`/api/regression-suites/${suiteId}/scope/${itemId}?is_excluded=${isExcluded}&reason=${encodeURIComponent(reason)}`, {
        method: "PATCH",
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update exclusion");
      }
      toast.success(isExcluded ? "Item excluded" : "Item restored");
      await loadSuiteData();
    } catch (err) {
      toast.error("Failed to update exclusion", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setIsUpdating(false);
    }
  };

  const handlePriorityChange = async (itemId: string, newPriority: string, reason: string) => {
    try {
      setIsUpdating(true);
      const res = await fetch(`/api/regression-suites/${suiteId}/scope/${itemId}?priority=${newPriority}&reason=${encodeURIComponent(reason)}`, {
        method: "PATCH",
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update priority");
      }
      toast.success("Priority updated");
      await loadSuiteData();
    } catch (err) {
      toast.error("Failed to update priority", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleExecutionStatusChange = async (itemId: string, newStatus: string, reason: string) => {
    try {
      setIsUpdating(true);
      const res = await fetch(`/api/regression-suites/${suiteId}/scope/${itemId}?execution_status=${newStatus}&reason=${encodeURIComponent(reason)}`, {
        method: "PATCH",
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update execution status");
      }
      toast.success("Execution status updated");
      await loadSuiteData();
    } catch (err) {
      toast.error("Failed to update execution status", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setIsUpdating(false);
    }
  };

  const openOverrideDialog = (itemId: string, action: string, currentValue: string) => {
    setOverrideDialog({ open: true, itemId, action, currentValue });
    setOverrideReason("");
  };

  const closeOverrideDialog = () => {
    setOverrideDialog({ open: false, itemId: null, action: "", currentValue: "" });
    setOverrideReason("");
  };

  const toggleOverrideHistory = (itemId: string) => {
    setExpandedOverrideItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(itemId)) {
        newSet.delete(itemId);
      } else {
        newSet.add(itemId);
      }
      return newSet;
    });
  };

  const submitOverride = async () => {
    if (!overrideDialog.itemId || !overrideReason.trim()) {
      toast.error("Reason is required");
      return;
    }

    switch (overrideDialog.action) {
      case "tier":
        await handleUpdateTier(overrideDialog.itemId, overrideDialog.currentValue, overrideReason);
        break;
      case "exclude":
        await handleExclude(overrideDialog.itemId, true, overrideReason);
        break;
      case "restore":
        await handleExclude(overrideDialog.itemId, false, overrideReason);
        break;
      case "priority":
        await handlePriorityChange(overrideDialog.itemId, overrideDialog.currentValue, overrideReason);
        break;
      case "execution_status":
        await handleExecutionStatusChange(overrideDialog.itemId, overrideDialog.currentValue, overrideReason);
        break;
    }

    closeOverrideDialog();
  };

  const renderScopeItem = (item: ScopeItem) => {
    const isManual = item.item_type === "MANUAL_TEST";
    const isExpanded = expandedOverrideItems.has(item.id);
    
    return (
      <Card key={item.id} className={`mb-2 ${item.is_excluded ? "opacity-50 border-red-200" : ""} ${isManual ? "border-purple-200 bg-purple-50/30" : ""}`}>
        <CardContent className="p-3">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                <Badge className={`text-[10px] px-1.5 py-0.5 ${getTierColor(item.tier)}`}>{item.tier.replace("_", " ")}</Badge>
                <Badge className={`text-[10px] px-1.5 py-0.5 ${getPriorityColor(item.priority)}`}>{item.priority}</Badge>
                <Badge variant={isManual ? "default" : "outline"} className={`text-[10px] px-1.5 py-0.5 ${isManual ? "bg-purple-600 text-white" : ""}`}>
                  {item.item_type.replace("_", " ")}
                </Badge>
                {getExecutionIcon(item.execution_status)}
                {item.is_excluded && <Badge variant="destructive" className="text-[10px] px-1.5 py-0.5">EXCLUDED</Badge>}
                {isManual && <Badge variant="outline" className="text-[10px] px-1.5 py-0.5 border-purple-300 text-purple-700">MANUAL</Badge>}
                {item.has_overrides && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0.5 border-amber-300 text-amber-700 flex items-center gap-1">
                    <History className="w-3 h-3" />
                    Modified
                  </Badge>
                )}
              </div>
              
              <div className="font-medium text-sm mb-1 truncate">
                {item.test_case?.test_name || 
                 item.external_test_case?.title || 
                 item.suggested_scenario?.title || 
                 "Unknown Item"}
              </div>
              
              <div className="flex items-center gap-2 text-[10px] text-gray-500 mb-1 flex-wrap">
                {item.behavior && (
                  <span className="flex items-center gap-1">
                    <Brain className="w-3 h-3" />
                    {item.behavior.name}
                  </span>
                )}
                {item.journey && (
                  <span className="flex items-center gap-1">
                    <Globe className="w-3 h-3" />
                    {item.journey.name}
                  </span>
                )}
                {item.coverage_status && (
                  <span className="flex items-center gap-1">
                    <Shield className="w-3 h-3" />
                    {item.coverage_status.replace("_", " ")}
                  </span>
                )}
                {item.external_test_case?.provider && (
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    {item.external_test_case.provider}
                  </span>
                )}
              </div>
              
              {item.selection_reason && (
                <div className="text-[10px] text-gray-400 line-clamp-1">
                  {item.selection_reason}
                </div>
              )}
              
              {/* Override History Expandable */}
              {item.has_overrides && (
                <div className="mt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleOverrideHistory(item.id)}
                    className="text-[10px] px-2 py-0.5 h-6 text-amber-700 hover:text-amber-800 hover:bg-amber-50"
                  >
                    {isExpanded ? (
                      <>
                        <ChevronUp className="w-3 h-3 mr-1" />
                        Hide History ({item.override_history.length})
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-3 h-3 mr-1" />
                        Show History ({item.override_history.length})
                      </>
                    )}
                  </Button>
                  
                  {isExpanded && (
                    <div className="mt-2 bg-amber-50 border border-amber-200 rounded p-2">
                      {item.override_history.map((override, idx) => (
                        <div key={override.id} className="text-[10px] mb-2 last:mb-0">
                          <div className="font-medium text-amber-900 mb-1">
                            {override.override_type.replace("_", " ")}
                          </div>
                          <div className="text-amber-700 mb-1">
                            <span className="font-medium">Reason:</span> {override.reason}
                          </div>
                          <div className="text-amber-600 mb-1">
                            <span className="font-medium">By:</span> {override.overridden_by || "Unknown"}
                          </div>
                          <div className="text-amber-600 mb-1">
                            <span className="font-medium">At:</span> {new Date(override.overridden_at).toLocaleString()}
                          </div>
                          {override.original_value && (
                            <div className="text-amber-600 mb-1">
                              <span className="font-medium">Original:</span> {JSON.stringify(override.original_value)}
                            </div>
                          )}
                          {override.new_value && (
                            <div className="text-amber-600">
                              <span className="font-medium">New:</span> {JSON.stringify(override.new_value)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            
            <div className="flex flex-col gap-1 shrink-0">
              <select
                value={item.tier}
                onChange={(e) => openOverrideDialog(item.id, "tier", e.target.value)}
                className="text-[10px] border rounded px-1.5 py-0.5 bg-white"
                disabled={isUpdating}
              >
                <option value="MUST_RUN">Must Run</option>
                <option value="SHOULD_RUN">Should Run</option>
                <option value="OPTIONAL">Optional</option>
              </select>
              
              <select
                value={item.priority}
                onChange={(e) => openOverrideDialog(item.id, "priority", e.target.value)}
                className="text-[10px] border rounded px-1.5 py-0.5 bg-white"
                disabled={isUpdating}
              >
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
              
              {isManual && (
                <select
                  value={item.execution_status}
                  onChange={(e) => openOverrideDialog(item.id, "execution_status", e.target.value)}
                  className="text-[10px] border rounded px-1.5 py-0.5 bg-white"
                  disabled={isUpdating}
                >
                  <option value="MANUAL_PENDING">Pending</option>
                  <option value="PASSED">Passed</option>
                  <option value="FAILED">Failed</option>
                  <option value="BLOCKED">Blocked</option>
                </select>
              )}
              
              <Button
                size="sm"
                variant={item.is_excluded ? "default" : "outline"}
                onClick={() => openOverrideDialog(item.id, item.is_excluded ? "restore" : "exclude", "")}
                className="text-[10px] px-2 py-0.5 h-6"
                disabled={isUpdating}
              >
                {item.is_excluded ? "Restore" : "Exclude"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  if (loading) {
    return (
      <div className="container mx-auto p-8">
        <div className="text-center">Loading regression suite...</div>
      </div>
    );
  }

  if (error || !suite) {
    return (
      <div className="container mx-auto p-8">
        <div className="text-center text-red-600">
          {error || "Suite not found"}
        </div>
      </div>
    );
  }

  const mustRunCount = scope?.grouped_by_tier.MUST_RUN.filter(i => !i.is_excluded).length || 0;
  const shouldRunCount = scope?.grouped_by_tier.SHOULD_RUN.filter(i => !i.is_excluded).length || 0;
  const optionalCount = scope?.grouped_by_tier.OPTIONAL.filter(i => !i.is_excluded).length || 0;
  const excludedCount = scope?.grouped_by_tier.EXCLUDED?.length || 0;
  const automatedTestsCount = scope?.all_items.filter(i => i.item_type === "AUTOMATED_TEST" && !i.is_excluded).length || 0;
  const manualTestsCount = scope?.all_items.filter(i => i.item_type === "MANUAL_TEST" && !i.is_excluded).length || 0;
  const suggestedScenariosCount = scope?.all_items.filter(i => i.item_type === "SUGGESTED_SCENARIO" && !i.is_excluded).length || 0;
  const coverageGapsCount = scope?.all_items.filter(i => i.item_type === "COVERAGE_GAP" && !i.is_excluded).length || 0;

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      {/* Override Reason Dialog */}
      <Dialog open={overrideDialog.open} onOpenChange={closeOverrideDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {overrideDialog.action === "tier" && "Change Tier"}
              {overrideDialog.action === "priority" && "Change Priority"}
              {overrideDialog.action === "exclude" && "Exclude Item"}
              {overrideDialog.action === "restore" && "Restore Item"}
              {overrideDialog.action === "execution_status" && "Update Execution Status"}
            </DialogTitle>
            <DialogDescription>
              Please provide a reason for this change. This will be recorded in the override history.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reason">Reason *</Label>
              <Textarea
                id="reason"
                placeholder="Explain why this change is necessary..."
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeOverrideDialog} disabled={isUpdating}>
              Cancel
            </Button>
            <Button onClick={submitOverride} disabled={isUpdating || !overrideReason.trim()}>
              {isUpdating ? "Applying..." : "Apply Change"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suite Header */}
      <div className="mb-6">
        <Button variant="ghost" onClick={() => router.back()} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h1 className="text-2xl font-bold mb-2">{suite.name}</h1>
            <p className="text-sm text-gray-600 mb-3">{suite.description}</p>
            
            <div className="flex items-center gap-3 text-xs text-gray-500 mb-3 flex-wrap">
              {suite.pull_request_id && (
                <span className="flex items-center gap-1">
                  <GitPullRequest className="w-3 h-3" />
                  PR #{suite.pull_request_id}
                </span>
              )}
              {suite.release_id && (
                <span className="flex items-center gap-1">
                  <GitBranch className="w-3 h-3" />
                  Release {suite.release_id}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Created {new Date(suite.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          
          <div className="flex gap-2">
            <Badge variant="outline" className="text-xs">{suite.suite_type.replace("_", " ")}</Badge>
            <Badge variant="outline" className="text-xs">{suite.status}</Badge>
            <Badge variant="outline" className="text-xs">Confidence: {suite.confidence_level}</Badge>
            <Badge variant="outline" className="text-xs">Score: {(suite.scope_score * 100).toFixed(0)}%</Badge>
          </div>
        </div>
        
        {/* Comprehensive Scope Summary */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          <Card className="bg-red-50 border-red-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-red-800">Must Run</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-red-600">{mustRunCount}</div>
            </CardContent>
          </Card>
          
          <Card className="bg-amber-50 border-amber-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-amber-800">Should Run</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-amber-600">{shouldRunCount}</div>
            </CardContent>
          </Card>
          
          <Card className="bg-gray-50 border-gray-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-gray-800">Optional</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-gray-600">{optionalCount}</div>
            </CardContent>
          </Card>
          
          <Card className="bg-slate-50 border-slate-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-slate-800">Excluded</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-slate-400">{excludedCount}</div>
            </CardContent>
          </Card>
        </div>
        
        {/* Type Breakdown */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          <Card className="bg-blue-50 border-blue-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-blue-800 flex items-center gap-1">
                <Layers className="w-3 h-3" />
                Automated
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-blue-600">{automatedTestsCount}</div>
            </CardContent>
          </Card>
          
          <Card className="bg-purple-50 border-purple-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-purple-800 flex items-center gap-1">
                <FileText className="w-3 h-3" />
                Manual
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-purple-600">{manualTestsCount}</div>
            </CardContent>
          </Card>
          
          <Card className="bg-green-50 border-green-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-green-800 flex items-center gap-1">
                <Zap className="w-3 h-3" />
                Scenarios
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-green-600">{suggestedScenariosCount}</div>
            </CardContent>
          </Card>
          
          <Card className="bg-orange-50 border-orange-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-orange-800 flex items-center gap-1">
                <Target className="w-3 h-3" />
                Gaps
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-orange-600">{coverageGapsCount}</div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Tabs defaultValue="must_run" className="w-full">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="must_run" className="text-xs">
            Must Run ({mustRunCount})
          </TabsTrigger>
          <TabsTrigger value="should_run" className="text-xs">
            Should Run ({shouldRunCount})
          </TabsTrigger>
          <TabsTrigger value="optional" className="text-xs">
            Optional ({optionalCount})
          </TabsTrigger>
          <TabsTrigger value="excluded" className="text-xs">
            Excluded ({excludedCount})
          </TabsTrigger>
          <TabsTrigger value="all" className="text-xs">
            All ({scope?.total_items || 0})
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="must_run" className="mt-4">
          {scope?.grouped_by_tier.MUST_RUN.filter(i => !i.is_excluded).map(renderScopeItem)}
          {mustRunCount === 0 && <div className="text-gray-500 text-center py-8 text-sm">No must-run items</div>}
        </TabsContent>
        
        <TabsContent value="should_run" className="mt-4">
          {scope?.grouped_by_tier.SHOULD_RUN.filter(i => !i.is_excluded).map(renderScopeItem)}
          {shouldRunCount === 0 && <div className="text-gray-500 text-center py-8 text-sm">No should-run items</div>}
        </TabsContent>
        
        <TabsContent value="optional" className="mt-4">
          {scope?.grouped_by_tier.OPTIONAL.filter(i => !i.is_excluded).map(renderScopeItem)}
          {optionalCount === 0 && <div className="text-gray-500 text-center py-8 text-sm">No optional items</div>}
        </TabsContent>
        
        <TabsContent value="excluded" className="mt-4">
          {scope?.grouped_by_tier.EXCLUDED?.map(renderScopeItem)}
          {excludedCount === 0 && <div className="text-gray-500 text-center py-8 text-sm">No excluded items</div>}
        </TabsContent>
        
        <TabsContent value="all" className="mt-4">
          {scope?.all_items.map(renderScopeItem)}
        </TabsContent>
      </Tabs>
    </div>
  );
}
