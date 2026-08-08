"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X,
  FileText,
  Users,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles,
  Plus,
  ChevronDown,
  ChevronRight,
  Layers,
  Trash2,
  Edit2
} from "lucide-react";
import { 
  RequirementPackageViewModel, 
  RequirementGroupViewModel, 
  AcceptanceCriterionViewModel,
  RequirementGroupType,
  ACSourceType,
  PackageStatus 
} from "@/types/requirements";

interface BusinessRequirementsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedReadiness: any, recommendationStale: boolean) => void;
  repositoryId: string;
  pullRequestId?: string;
  initialData?: {
    business_change?: string;
    affected_users?: string;
    acceptance_criteria?: string;
    risk_notes?: string;
    testing_notes?: string;
  };
}

export default function BusinessRequirementsModal({ 
  isOpen, 
  onClose, 
  onSuccess,
  repositoryId,
  pullRequestId,
  initialData
}: BusinessRequirementsModalProps) {
  const [mode, setMode] = useState<"quick_paste" | "structured_review">("quick_paste");
  const [formData, setFormData] = useState({
    business_change: "",
    affected_users: "",
    acceptance_criteria: "",
    risk_notes: "",
    testing_notes: "",
  });
  
  const [requirementPackage, setRequirementPackage] = useState<RequirementPackageViewModel>({
    repositoryId,
    pullRequestId: pullRequestId || "",
    status: "NEEDS_REVIEW",
    groups: [],
    readiness: {
      status: "NEEDS_REVIEW",
      groupCount: 0,
      acCount: 0,
      stableIdCoverage: "0/0",
      duplicateCount: 0,
      needsReviewCount: 0,
      generatedUnacceptedCount: 0,
      flatteningRisk: "HIGH",
      requiredFixes: []
    }
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (isOpen) {
      setFormData({
        business_change: initialData?.business_change || "",
        affected_users: initialData?.affected_users || "",
        acceptance_criteria: initialData?.acceptance_criteria || "",
        risk_notes: initialData?.risk_notes || "",
        testing_notes: initialData?.testing_notes || "",
      });
      setMode("quick_paste");
      setError(null);
      setSuccess(false);
      setRequirementPackage({
        repositoryId,
        pullRequestId: pullRequestId || "",
        status: "NEEDS_REVIEW",
        groups: [],
        readiness: {
          status: "NEEDS_REVIEW",
          groupCount: 0,
          acCount: 0,
          stableIdCoverage: "0/0",
          duplicateCount: 0,
          needsReviewCount: 0,
          generatedUnacceptedCount: 0,
          flatteningRisk: "HIGH",
          requiredFixes: []
        }
      });
    }
  }, [isOpen, initialData, repositoryId, pullRequestId]);

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  /**
   * Strict section-aware parser. Only numbered/bulleted lines inside the
   * "Acceptance Criteria:" section become ACs. Everything else is classified
   * into its own bucket and NEVER becomes an AC.
   */
  const parseRequirements = (text: string): RequirementGroupViewModel[] => {
    // ── 1. Section header detection (anchored to start of trimmed line) ──────
    const SECTION_HEADER_PATTERNS: Record<string, RegExp> = {
      businessChange:    /^Business\s+Change\s*:/i,
      businessSummary:   /^Business\s+Summary\s*:/i,
      affectedJourneys:  /^Affected\s+(?:journeys|users|flows)\s*:/i,
      acceptanceCriteria:/^Acceptance\s+Criter(?:ia|ion)\s*:/i,
      invalidTestData:   /^Invalid\s+(?:test\s+data|data)\s*(?:examples?)?\s*:/i,
      validTestData:     /^Valid\s+(?:test\s+data|data)\s*(?:examples?)?\s*:/i,
      securityNotes:     /^Security\s+(?:notes?)?\s*:/i,
      integrationNotes:  /^Integration\s+(?:notes?)?\s*:/i,
      apiNotes:          /^API\s+(?:notes?)?\s*:/i,
      riskNotes:         /^Risk\s+(?:notes?)?\s*:/i,
      outOfScope:        /^Out\s+of\s+scope\s*:/i,
      notes:             /^Notes?\s*:/i,
      assumptions:       /^Assumptions?\s*:/i,
    };

    // AC section terminators (stop collecting ACs when any of these appear)
    const AC_STOP_SECTIONS = new Set([
      "invalidTestData", "validTestData", "securityNotes",
      "integrationNotes", "apiNotes", "riskNotes", "outOfScope",
      "notes", "assumptions",
    ]);

    // Valid AC line pattern: must start with number/AC-id
    const AC_LINE_PATTERN = /^(?:\d+[\.\)]\s+|AC[-\s]?\d+\s*[-:]?\s*)/i;
    // Captures the original source number from either "NN." or "AC-NN" prefixes
    const AC_NUMBER_PATTERN = /^(?:(\d+)[\.\)]\s+|AC[-\s]?(\d+)\s*[-:]?\s*)/i;

    // ── 2. Parse into buckets ─────────────────────────────────────────────────
    const buckets: Record<string, string[]> = {
      businessChangeSummary: [],
      affectedJourneys: [],
      acceptanceCriteria: [],
      invalidTestDataExamples: [],
      validTestDataExamples: [],
      securityNotes: [],
      riskNotes: [],
      integrationNotes: [],
      outOfScopeNotes: [],
      rejected: [],
    };
    // Parallel array holding the original source number (or null) for each
    // entry pushed into buckets.acceptanceCriteria, preserving upload order.
    const acSourceNumbers: (number | null)[] = [];

    const BUCKET_MAP: Record<string, string> = {
      businessChange:    "businessChangeSummary",
      businessSummary:   "businessChangeSummary",
      affectedJourneys:  "affectedJourneys",
      acceptanceCriteria:"acceptanceCriteria",
      invalidTestData:   "invalidTestDataExamples",
      validTestData:     "validTestDataExamples",
      securityNotes:     "securityNotes",
      integrationNotes:  "integrationNotes",
      apiNotes:          "integrationNotes",
      riskNotes:         "riskNotes",
      outOfScope:        "outOfScopeNotes",
      notes:             "outOfScopeNotes",
      assumptions:       "outOfScopeNotes",
    };

    let currentSection: string | null = null;
    let inACSection = false;

    for (const raw of text.split("\n")) {
      const trimmed = raw.trim();
      if (!trimmed) continue;

      // Detect section header
      let detectedSection: string | null = null;
      for (const [name, pattern] of Object.entries(SECTION_HEADER_PATTERNS)) {
        if (pattern.test(trimmed)) {
          detectedSection = name;
          break;
        }
      }

      if (detectedSection !== null) {
        currentSection = detectedSection;
        inACSection = detectedSection === "acceptanceCriteria";

        // If entering a stop-section, end AC collection
        if (AC_STOP_SECTIONS.has(detectedSection)) {
          inACSection = false;
        }

        // Capture inline content after colon (e.g. "Business Change: text here")
        const colonIdx = trimmed.indexOf(":");
        if (colonIdx !== -1) {
          const after = trimmed.slice(colonIdx + 1).trim();
          if (after && currentSection) {
            const bucket = BUCKET_MAP[currentSection] ?? "rejected";
            if (bucket !== "acceptanceCriteria") {
              buckets[bucket].push(after);
            }
          }
        }
        continue;
      }

      // No section detected — classify based on current section
      if (!currentSection) {
        buckets.rejected.push(trimmed);
        continue;
      }

      // Stop collecting ACs if we hit a stop section
      if (AC_STOP_SECTIONS.has(currentSection)) {
        inACSection = false;
      }

      const targetBucket = BUCKET_MAP[currentSection] ?? "rejected";

      if (targetBucket === "acceptanceCriteria") {
        // STRICT: only accept numbered/AC-id lines
        if (!inACSection) {
          buckets.rejected.push(trimmed);
          continue;
        }
        if (AC_LINE_PATTERN.test(trimmed)) {
          // Capture the original source number before stripping the prefix
          const numberMatch = trimmed.match(AC_NUMBER_PATTERN);
          const sourceNumber = numberMatch
            ? parseInt(numberMatch[1] ?? numberMatch[2], 10)
            : null;
          // Strip the numbering prefix
          const acText = trimmed
            .replace(/^\d+[\.\)]\s+/, "")
            .replace(/^AC[-\s]?\d+\s*[-:]?\s*/i, "")
            .trim();
          if (acText.length > 3) {
            buckets.acceptanceCriteria.push(acText);
            acSourceNumbers.push(sourceNumber);
          } else {
            buckets.rejected.push(trimmed);
          }
        } else {
          // Line inside AC section but not numbered → reject
          buckets.rejected.push(trimmed);
        }
      } else {
        // List bullet/number stripping for non-AC buckets
        const cleanLine = trimmed
          .replace(/^[\-\*\+]\s+/, "")
          .replace(/^\d+[\.\)]\s+/, "")
          .trim();
        if (cleanLine) buckets[targetBucket].push(cleanLine);
      }
    }

    // ── 3. Update package state with separated sections ───────────────────────
    setRequirementPackage(prev => ({
      ...prev,
      businessChangeSummary: buckets.businessChangeSummary[0] ?? prev.summary,
      affectedJourneys: buckets.affectedJourneys,
      invalidTestDataExamples: buckets.invalidTestDataExamples,
      validTestDataExamples: buckets.validTestDataExamples,
      securityNotes: buckets.securityNotes,
    }));

    // ── 4. Build groups from AC lines only ────────────────────────────────────
    const acLines = buckets.acceptanceCriteria;
    const affectedJourneys = buckets.affectedJourneys;
    const groups: RequirementGroupViewModel[] = [];

    if (acLines.length === 0) return groups;

    // Try to group by affected journeys using keyword matching
    if (affectedJourneys.length > 0) {
      const assigned = new Set<number>();

      affectedJourneys.forEach((journey: string, jIdx: number) => {
        // Build a set of keywords from the journey name
        const keywords = journey.toLowerCase().split(/[\s\-\/]+/).filter(w => w.length > 2);
        const journeyACs: AcceptanceCriterionViewModel[] = [];

        acLines.forEach((ac: string, acIdx: number) => {
          if (assigned.has(acIdx)) return;
          const acLower = ac.toLowerCase();
          const matches = keywords.some(kw => acLower.includes(kw));
          if (matches) {
            assigned.add(acIdx);
            journeyACs.push({
              id: `ac-${jIdx}-${acIdx}`,
              title: ac,
              sourceType: "MANUAL",
              status: "ACTIVE",
              sourceNumber: acSourceNumbers[acIdx] ?? undefined,
            });
          }
        });

        // Preserve original upload order within the group; grouping must
        // never renumber ACs (display ref is derived from sourceNumber).
        journeyACs.sort((a, b) => (a.sourceNumber ?? 0) - (b.sourceNumber ?? 0));

        if (journeyACs.length > 0) {
          groups.push({
            id: `group-${jIdx + 1}`,
            groupNumber: (jIdx + 1).toString(),
            title: journey,
            groupType: "ENHANCEMENT",
            status: "ACTIVE",
            acceptanceCriteria: journeyACs,
          });
        }
      });

      // Remaining unassigned ACs → General Requirements
      const remaining = acLines
        .map((ac: string, idx: number) => ({ ac, idx }))
        .filter(({ idx }) => !assigned.has(idx))
        .sort((a, b) => (acSourceNumbers[a.idx] ?? 0) - (acSourceNumbers[b.idx] ?? 0));

      if (remaining.length > 0) {
        groups.push({
          id: `group-general`,
          groupNumber: (groups.length + 1).toString(),
          title: "General Requirements",
          groupType: "ENHANCEMENT",
          status: "ACTIVE",
          acceptanceCriteria: remaining.map(({ ac, idx }) => ({
            id: `ac-general-${idx}`,
            title: ac,
            sourceType: "MANUAL",
            status: "ACTIVE",
            sourceNumber: acSourceNumbers[idx] ?? undefined,
          })),
        });
      }
    } else {
      // No journeys — single General Requirements group
      groups.push({
        id: "group-default",
        groupNumber: "1",
        title: "General Requirements",
        groupType: "ENHANCEMENT",
        status: "ACTIVE",
        acceptanceCriteria: acLines.map((ac: string, idx: number) => ({
          id: `ac-${idx + 1}`,
          title: ac,
          sourceType: "MANUAL",
          status: "ACTIVE",
          sourceNumber: acSourceNumbers[idx] ?? undefined,
        })),
      });
    }

    return groups;
  };

  const determineGroupType = (text: string): RequirementGroupType => {
    const lower = text.toLowerCase();
    if (lower.includes("bug")) return "BUG_FIX";
    if (lower.includes("tech") || lower.includes("debt")) return "TECH_DEBT";
    if (lower.includes("security")) return "SECURITY";
    if (lower.includes("non-functional") || lower.includes("nfr")) return "NON_FUNCTIONAL";
    return "ENHANCEMENT";
  };

  const handleParseAndReview = () => {
    console.log("[INPUT_2_PARSE_START]", { textLength: formData.acceptance_criteria.length });
    setIsParsing(true);
    setError(null);

    try {
      const parsedGroups = parseRequirements(formData.acceptance_criteria);
      console.log("[INPUT_2_PARSE_RESULT]", { groupsCount: parsedGroups.length, totalACs: parsedGroups.reduce((sum, g) => sum + g.acceptanceCriteria.length, 0) });
      
      const newPackage: RequirementPackageViewModel = {
        repositoryId,
        pullRequestId: pullRequestId || "",
        status: "NEEDS_REVIEW" as PackageStatus,
        summary: formData.business_change,
        affectedUsersOrJourneys: formData.affected_users,
        riskNotes: formData.risk_notes,
        groups: parsedGroups,
        readiness: calculateReadiness(parsedGroups)
      };

      setRequirementPackage(newPackage);
      setMode("structured_review");
      
      // Auto-expand first group
      if (parsedGroups.length > 0) {
        setExpandedGroups(new Set([parsedGroups[0].id || ""]));
      }
    } catch (err) {
      console.error("[INPUT_2_PARSE_ERROR]", err);
      setError(err instanceof Error ? err.message : "Failed to parse requirements");
    } finally {
      setIsParsing(false);
    }
  };

  const calculateReadiness = (groups: RequirementGroupViewModel[]) => {
    const acCount = groups.reduce((sum, g) => sum + g.acceptanceCriteria.length, 0);
    const needsReviewCount = groups.reduce((sum, g) => 
      sum + g.acceptanceCriteria.filter(ac => ac.status === "NEEDS_REVIEW").length, 0);
    const duplicateCount = groups.reduce((sum, g) => 
      sum + g.acceptanceCriteria.filter(ac => ac.status === "DUPLICATE").length, 0);
    
    return {
      status: (acCount > 0 ? "READY" : "NEEDS_REVIEW") as PackageStatus,
      groupCount: groups.length,
      acCount,
      stableIdCoverage: `${acCount}/${acCount}`,
      duplicateCount,
      needsReviewCount,
      generatedUnacceptedCount: 0,
      flatteningRisk: (groups.length > 1 ? "LOW" : "HIGH") as "LOW" | "HIGH",
      requiredFixes: groups.length === 0 ? ["Add requirement groups"] : []
    };
  };

  const handleAddGroup = () => {
    const newGroup: RequirementGroupViewModel = {
      id: `group-${Date.now()}`,
      groupNumber: (requirementPackage.groups.length + 1).toString(),
      title: "New Requirement Group",
      groupType: "ENHANCEMENT",
      status: "ACTIVE",
      acceptanceCriteria: []
    };
    setRequirementPackage(prev => ({
      ...prev,
      groups: [...prev.groups, newGroup]
    }));
    setExpandedGroups(prev => new Set([...prev, newGroup.id || ""]));
  };

  const handleDeleteGroup = (groupId: string) => {
    setRequirementPackage(prev => ({
      ...prev,
      groups: prev.groups.filter(g => g.id !== groupId)
    }));
  };

  const handleAddAC = (groupId: string) => {
    setRequirementPackage(prev => ({
      ...prev,
      groups: prev.groups.map(g => {
        if (g.id === groupId) {
          return {
            ...g,
            acceptanceCriteria: [
              ...g.acceptanceCriteria,
              {
                id: `ac-${Date.now()}`,
                title: "",
                sourceType: "MANUAL",
                status: "ACTIVE"
              }
            ]
          };
        }
        return g;
      })
    }));
  };

  const handleDeleteAC = (groupId: string, acId: string) => {
    setRequirementPackage(prev => ({
      ...prev,
      groups: prev.groups.map(g => {
        if (g.id === groupId) {
          return {
            ...g,
            acceptanceCriteria: g.acceptanceCriteria.filter(ac => ac.id !== acId)
          };
        }
        return g;
      })
    }));
  };

  const handleACChange = (groupId: string, acId: string, field: string, value: string) => {
    setRequirementPackage(prev => ({
      ...prev,
      groups: prev.groups.map(g => {
        if (g.id === groupId) {
          return {
            ...g,
            acceptanceCriteria: g.acceptanceCriteria.map(ac => {
              if (ac.id === acId) {
                return { ...ac, [field]: value };
              }
              return ac;
            })
          };
        }
        return g;
      })
    }));
  };

  const handleGroupChange = (groupId: string, field: string, value: string) => {
    setRequirementPackage(prev => ({
      ...prev,
      groups: prev.groups.map(g => {
        if (g.id === groupId) {
          return { ...g, [field]: value };
        }
        return g;
      })
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    console.log("[INPUT_2_HANDLE_SUBMIT]", { mode, isSubmitting, groupsCount: requirementPackage.groups.length });
    
    // Validate
    if (mode === "quick_paste") {
      if (!formData.business_change.trim()) {
        setError("Business change summary is required");
        return;
      }
      if (!formData.acceptance_criteria.trim()) {
        setError("Acceptance criteria is required");
        return;
      }
    } else {
      if (requirementPackage.groups.length === 0) {
        setError("At least one requirement group is required");
        return;
      }
      const hasEmptyGroup = requirementPackage.groups.some(g => 
        !g.title.trim() || g.acceptanceCriteria.length === 0
      );
      if (hasEmptyGroup) {
        setError("Each group must have a title and at least one acceptance criterion");
        return;
      }
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const payload = mode === "quick_paste" ? {
        business_change: formData.business_change,
        affected_users: formData.affected_users,
        acceptance_criteria: formData.acceptance_criteria,
        risk_notes: formData.risk_notes,
        testing_notes: formData.testing_notes,
      } : {
        business_change_summary: formData.business_change,
        affected_users_or_journeys: formData.affected_users,
        risk_notes: formData.risk_notes,
        requirement_groups: requirementPackage.groups.map(g => ({
          title: g.title,
          group_type: g.groupType,
          business_flow: g.businessFlow,
          risk_level: g.riskLevel,
          acceptance_criteria: g.acceptanceCriteria.map(ac => ({
            title: ac.title,
            description: ac.description,
            source_type: ac.sourceType,
            status: ac.status,
            source_number: ac.sourceNumber
          }))
        }))
      };

      console.log("[INPUT_2_SAVE_PAYLOAD]", {
        mode,
        repositoryId,
        pullRequestId,
        groupsCount: payload.requirement_groups?.length || 0,
        totalACs: payload.requirement_groups?.reduce((sum, g) => sum + g.acceptance_criteria.length, 0) || 0,
      });

      const response = await fetch(`/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/acceptance-criteria/manual`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        console.error("[INPUT_2_SAVE_ERROR]", errData);
        throw new Error(errData.error || `Failed to submit: ${response.status}`);
      }

      const updatedReadiness = await response.json();
      console.log("[INPUT_2_SAVE_SUCCESS]", updatedReadiness);
      setSuccess(true);
      onSuccess(updatedReadiness, true);
      onClose();
      setSuccess(false);
    } catch (err) {
      console.error("[INPUT_2_SAVE_EXCEPTION]", err);
      setError(err instanceof Error ? err.message : "Failed to save requirements");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (isSubmitting || isParsing) return;
    onClose();
  };

  const toggleGroup = (groupId: string) => {
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(groupId)) {
        newSet.delete(groupId);
      } else {
        newSet.add(groupId);
      }
      return newSet;
    });
  };

  const getGroupTypeColor = (type: RequirementGroupType) => {
    switch (type) {
      case "ENHANCEMENT": return "text-emerald-400";
      case "BUG_FIX": return "text-rose-400";
      case "TECH_DEBT": return "text-amber-400";
      case "SECURITY": return "text-purple-400";
      case "NON_FUNCTIONAL": return "text-blue-400";
      default: return "text-zinc-400";
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleCancel}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          />

          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div 
              initial={{ scale: 0.96, y: 15, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.96, y: 15, opacity: 0 }}
              transition={{ type: "spring", duration: 0.4 }}
              className="bg-zinc-950 border border-zinc-800/80 rounded-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden pointer-events-auto shadow-2xl shadow-black/80"
            >
              <div className="flex items-center justify-between p-6 border-b border-zinc-900 bg-zinc-950">
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-indigo-400" />
                  <h2 className="text-xl font-bold text-white tracking-tight">Business Requirements & Acceptance Criteria</h2>
                </div>
                <Button variant="ghost" size="icon" onClick={handleCancel} disabled={isSubmitting} className="text-zinc-400 hover:text-white rounded-lg">
                  <X className="w-5 h-5" />
                </Button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {success ? (
                  <div className="text-center py-16 space-y-4">
                    <motion.div
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 200, damping: 15 }}
                    >
                      <CheckCircle2 className="w-16 h-16 text-emerald-400 mx-auto" />
                    </motion.div>
                    <h3 className="text-lg font-bold text-white tracking-tight">Requirements Saved</h3>
                    <p className="text-zinc-400 text-sm max-w-sm mx-auto leading-relaxed">
                      Your business requirements have been saved. Regenerate the recommendation to include requirement coverage.
                    </p>
                  </div>
                ) : mode === "quick_paste" ? (
                  <form id="requirements-form" onSubmit={handleParseAndReview} className="space-y-5">
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Business Change Summary <span className="text-rose-400">*</span>
                      </label>
                      <textarea
                        value={formData.business_change}
                        onChange={(e) => handleInputChange('business_change', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none"
                        rows={3}
                        placeholder="Describe what this change accomplishes in business terms..."
                        required
                      />
                    </div>

                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Affected Users/Journeys <span className="text-zinc-500 font-normal">(optional)</span>
                      </label>
                      <div className="flex items-center gap-2 px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus-within:border-zinc-700 rounded-xl transition-colors">
                        <Users className="w-4 h-4 text-zinc-500 shrink-0" />
                        <input
                          type="text"
                          value={formData.affected_users}
                          onChange={(e) => handleInputChange('affected_users', e.target.value)}
                          className="flex-1 bg-transparent text-zinc-100 text-sm focus:outline-none placeholder-zinc-600"
                          placeholder="e.g., Customer checkout, Admin settings, Mobile users"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Paste Requirements / Acceptance Criteria <span className="text-rose-400">*</span>
                      </label>
                      <textarea
                        value={formData.acceptance_criteria}
                        onChange={(e) => handleInputChange('acceptance_criteria', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none font-mono"
                        rows={8}
                        placeholder="Enhancement 1: Password validation during sign-up&#10;AC-01 Weak passwords are rejected during sign-up.&#10;AC-02 Strong passwords are accepted during sign-up.&#10;&#10;Enhancement 2: Password reset behavior&#10;AC-03 Expired reset tokens are rejected."
                        required
                      />
                      <p className="text-xs text-zinc-500">
                        The system will parse this into requirement groups. Use "Enhancement N:" or "# Heading" to create groups.
                      </p>
                    </div>

                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-zinc-400 uppercase tracking-wider">
                        Risk Notes <span className="text-zinc-500 font-normal">(optional)</span>
                      </label>
                      <textarea
                        value={formData.risk_notes}
                        onChange={(e) => handleInputChange('risk_notes', e.target.value)}
                        className="w-full px-3.5 py-2.5 bg-zinc-900/60 border border-zinc-800 focus:border-zinc-700 rounded-xl text-zinc-100 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-700 placeholder-zinc-600 transition-colors resize-none"
                        rows={2}
                        placeholder="Potential risks, edge cases, or areas requiring special attention..."
                      />
                    </div>

                    {error && (
                      <motion.div 
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-rose-950/10 border border-rose-900/30 rounded-xl p-4 flex gap-3 items-start"
                      >
                        <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-semibold text-rose-200">Error</p>
                          <p className="text-xs text-rose-300 mt-0.5">{error}</p>
                        </div>
                      </motion.div>
                    )}
                  </form>
                ) : (
                  <div className="space-y-6">
                    <div className="bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Layers className="w-4 h-4 text-zinc-400" />
                        <h3 className="font-semibold text-zinc-200">Detected Requirements</h3>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <div className="text-zinc-500">Requirement Groups</div>
                          <div className="text-zinc-200 font-medium">{requirementPackage.readiness.groupCount}</div>
                        </div>
                        <div>
                          <div className="text-zinc-500">Acceptance Criteria</div>
                          <div className="text-zinc-200 font-medium">{requirementPackage.readiness.acCount}</div>
                        </div>
                        <div>
                          <div className="text-zinc-500">Stable IDs</div>
                          <div className="text-zinc-200 font-medium">{requirementPackage.readiness.stableIdCoverage}</div>
                        </div>
                        <div>
                          <div className="text-zinc-500">Duplicates</div>
                          <div className="text-zinc-200 font-medium">{requirementPackage.readiness.duplicateCount}</div>
                        </div>
                      </div>
                      {(requirementPackage.invalidTestDataExamples?.length || 
                        requirementPackage.validTestDataExamples?.length || 
                        requirementPackage.securityNotes?.length) && (
                        <div className="mt-4 pt-4 border-t border-zinc-800/50 grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                          {requirementPackage.invalidTestDataExamples && requirementPackage.invalidTestDataExamples.length > 0 && (
                            <div>
                              <div className="text-zinc-500">Invalid Test Data</div>
                              <div className="text-zinc-200 font-medium">{requirementPackage.invalidTestDataExamples.length}</div>
                            </div>
                          )}
                          {requirementPackage.validTestDataExamples && requirementPackage.validTestDataExamples.length > 0 && (
                            <div>
                              <div className="text-zinc-500">Valid Test Data</div>
                              <div className="text-zinc-200 font-medium">{requirementPackage.validTestDataExamples.length}</div>
                            </div>
                          )}
                          {requirementPackage.securityNotes && requirementPackage.securityNotes.length > 0 && (
                            <div>
                              <div className="text-zinc-500">Security Notes</div>
                              <div className="text-zinc-200 font-medium">{requirementPackage.securityNotes.length}</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex justify-between items-center">
                      <h3 className="font-semibold text-zinc-200">Requirement Groups</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleAddGroup}
                        className="border-zinc-700 hover:border-zinc-600 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-xs"
                      >
                        <Plus className="w-3 h-3 mr-1" />
                        Add Group
                      </Button>
                    </div>

                    <div className="space-y-3">
                      {requirementPackage.groups.map((group) => (
                        <div key={group.id} className="bg-zinc-900/40 border border-zinc-800 rounded-lg overflow-hidden">
                          <div
                            onClick={() => toggleGroup(group.id || "")}
                            className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors cursor-pointer"
                          >
                            <div className="flex items-center gap-3">
                              {expandedGroups.has(group.id || "") ? (
                                <ChevronDown className="w-4 h-4 text-zinc-400" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-zinc-400" />
                              )}
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${getGroupTypeColor(group.groupType)} bg-zinc-800/50`}>
                                {group.groupType}
                              </span>
                              <input
                                type="text"
                                value={group.title}
                                onChange={(e) => handleGroupChange(group.id || "", "title", e.target.value)}
                                onClick={(e) => e.stopPropagation()}
                                className="font-medium text-zinc-200 bg-transparent border-none focus:outline-none focus:ring-0"
                              />
                              <span className="text-zinc-500 text-sm">({group.acceptanceCriteria.length} ACs)</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={(e) => { e.stopPropagation(); handleDeleteGroup(group.id || ""); }}
                                className="text-zinc-500 hover:text-rose-400 rounded-lg"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>

                          {expandedGroups.has(group.id || "") && (
                            <div className="px-4 pb-4 pt-2 border-t border-zinc-800/50 space-y-2">
                              <div className="space-y-2">
                                {group.acceptanceCriteria.map((ac) => (
                                  <div key={ac.id} className="bg-zinc-800/30 rounded-lg p-3">
                                    <div className="flex items-start gap-2">
                                      <input
                                        type="text"
                                        value={ac.title}
                                        onChange={(e) => handleACChange(group.id || "", ac.id || "", "title", e.target.value)}
                                        className="flex-1 text-sm text-zinc-300 bg-transparent border-none focus:outline-none focus:ring-0 placeholder-zinc-600"
                                        placeholder="Acceptance criterion text..."
                                      />
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => handleDeleteAC(group.id || "", ac.id || "")}
                                        className="text-zinc-500 hover:text-rose-400 rounded-lg shrink-0"
                                      >
                                        <Trash2 className="w-3 h-3" />
                                      </Button>
                                    </div>
                                  </div>
                                ))}
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleAddAC(group.id || "")}
                                  className="w-full border border-dashed border-zinc-700 hover:border-zinc-600 text-zinc-500 hover:text-zinc-300 rounded-lg text-xs"
                                >
                                  <Plus className="w-3 h-3 mr-1" />
                                  Add Acceptance Criterion
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    {error && (
                      <motion.div 
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-rose-950/10 border border-rose-900/30 rounded-xl p-4 flex gap-3 items-start"
                      >
                        <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                        <div>
                          <p className="text-xs font-semibold text-rose-200">Error</p>
                          <p className="text-xs text-rose-300 mt-0.5">{error}</p>
                        </div>
                      </motion.div>
                    )}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between p-6 border-t border-zinc-900 bg-zinc-950">
                <div className="text-xs text-zinc-500 max-w-[280px] leading-relaxed">
                  {mode === "quick_paste" 
                    ? "Paste your requirements and we'll parse them into groups."
                    : "Review and edit grouped requirements before saving."}
                </div>
                <div className="flex gap-3">
                  <Button 
                    type="button" 
                    variant="ghost" 
                    onClick={mode === "structured_review" ? () => setMode("quick_paste") : handleCancel}
                    disabled={isSubmitting || isParsing}
                    className="text-zinc-400 hover:text-white rounded-lg"
                  >
                    {mode === "structured_review" ? "Back" : "Cancel"}
                  </Button>
                  {mode === "quick_paste" ? (
                    <Button 
                      type="submit"
                      form="requirements-form"
                      disabled={isParsing}
                      className="bg-white text-zinc-950 hover:bg-zinc-100 rounded-lg font-semibold tracking-tight shadow-md shadow-white/5 active:scale-[0.98] transition-all"
                    >
                      {isParsing ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Parsing...
                        </>
                      ) : (
                        "Parse & Review"
                      )}
                    </Button>
                  ) : (
                    <Button 
                      type="button"
                      onClick={() => {
                        console.log("[INPUT_2_BUTTON_CLICKED]", { mode, isSubmitting, groupsCount: requirementPackage.groups.length });
                        handleSubmit(new Event("submit") as any);
                      }}
                      disabled={isSubmitting}
                      className="bg-white text-zinc-950 hover:bg-zinc-100 rounded-lg font-semibold tracking-tight shadow-md shadow-white/5 active:scale-[0.98] transition-all"
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        "Save & Recalculate"
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
