"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  AlertTriangle,
  Info,
  FileText,
  Users,
  TestTube,
  History,
  Plus,
  ChevronDown,
  ChevronUp
} from "lucide-react";

interface MissingIntelligenceItem {
  id: string;
  title: string;
  description: string;
  impact: string;
  action: string;
  isRequired: boolean;
  icon: React.ReactNode;
  onAction?: () => void;
}

interface MissingIntelligenceProps {
  items: MissingIntelligenceItem[];
  className?: string;
}

export default function MissingIntelligence({ items, className = "" }: MissingIntelligenceProps) {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  if (!items || items.length === 0) {
    return null;
  }

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedItems(newExpanded);
  };

  const requiredItems = items.filter(item => item.isRequired);
  const optionalItems = items.filter(item => !item.isRequired);

  return (
    <div className={`bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-5 ${className}`}>
      <div className="flex items-center gap-3 mb-4">
        <AlertTriangle className="w-5 h-5 text-amber-400" />
        <h3 className="text-sm font-medium text-zinc-300">Missing Intelligence</h3>
        <span className="text-xs text-zinc-500">
          {requiredItems.length > 0 && `${requiredItems.length} required`}
          {requiredItems.length > 0 && optionalItems.length > 0 && ", "}
          {optionalItems.length > 0 && `${optionalItems.length} optional`}
        </span>
      </div>

      <div className="space-y-3">
        {/* Required Items */}
        {requiredItems.map((item) => (
          <MissingIntelligenceItemComponent
            key={item.id}
            item={item}
            isExpanded={expandedItems.has(item.id)}
            onToggleExpanded={() => toggleExpanded(item.id)}
          />
        ))}

        {/* Optional Items */}
        {optionalItems.map((item) => (
          <MissingIntelligenceItemComponent
            key={item.id}
            item={item}
            isExpanded={expandedItems.has(item.id)}
            onToggleExpanded={() => toggleExpanded(item.id)}
          />
        ))}
      </div>

      {items.length > 3 && (
        <div className="mt-4 pt-3 border-t border-zinc-800/60">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              const allIds = items.map(item => item.id);
              setExpandedItems(
                expandedItems.size === items.length 
                  ? new Set() 
                  : new Set(allIds)
              );
            }}
            className="text-zinc-400 hover:text-white text-xs"
          >
            {expandedItems.size === items.length ? (
              <>
                <ChevronUp className="w-3 h-3 mr-1" />
                Collapse All
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3 mr-1" />
                Expand All
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

interface MissingIntelligenceItemComponentProps {
  item: MissingIntelligenceItem;
  isExpanded: boolean;
  onToggleExpanded: () => void;
}

function MissingIntelligenceItemComponent({ 
  item, 
  isExpanded, 
  onToggleExpanded 
}: MissingIntelligenceItemComponentProps) {
  return (
    <div className="bg-zinc-800/40 rounded-lg border border-zinc-700/50">
      <div className="p-3">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            <div className={`p-2 rounded-lg ${
              item.isRequired 
                ? "bg-rose-950/20 border border-rose-800/30" 
                : "bg-amber-950/20 border border-amber-800/30"
            }`}>
              {item.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="text-sm font-medium text-zinc-300">{item.title}</h4>
                {item.isRequired && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-500/20 text-rose-400 border border-rose-800/30">
                    Required
                  </span>
                )}
                {!item.isRequired && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-800/30">
                    Optional
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 mb-2">{item.description}</p>
              
              {isExpanded && (
                <div className="space-y-2 mt-3 pt-3 border-t border-zinc-700/50">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-3 h-3 text-amber-400 mt-0.5" />
                    <div>
                      <p className="text-xs font-medium text-zinc-300">Impact</p>
                      <p className="text-xs text-zinc-400">{item.impact}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-2">
                    <Info className="w-3 h-3 text-blue-400 mt-0.5" />
                    <div>
                      <p className="text-xs font-medium text-zinc-300">Action</p>
                      <p className="text-xs text-zinc-400">{item.action}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2 ml-3">
            {item.onAction && (
              <Button
                size="sm"
                variant="outline"
                onClick={item.onAction}
                className="text-xs h-7 px-2"
              >
                <Plus className="w-3 h-3 mr-1" />
                Add
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleExpanded}
              className="h-7 w-7"
            >
              {isExpanded ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper function to create missing intelligence items
export function createMissingIntelligenceItems(
  run: any,
  onAddAcceptanceCriteria?: () => void,
  onLinkWorkItem?: () => void,
  onAddManualTests?: () => void
) {
  const items: MissingIntelligenceItem[] = [];

  // Check for missing acceptance criteria
  const isAcStale = run.input_stale && run.stale_input_types?.includes("acceptance_criteria");
  if (!isAcStale && (!run.business_intent || !run.business_intent.has_business_intent)) {
    items.push({
      id: "acceptance_criteria",
      title: "Acceptance Criteria Missing",
      description: "No clear acceptance criteria or business intent found for this PR",
      impact: "Recommendation confidence is reduced without clear requirements",
      action: "Paste acceptance criteria to improve recommendation accuracy",
      isRequired: true,
      icon: <FileText className="w-4 h-4 text-rose-400" />,
      onAction: onAddAcceptanceCriteria
    });
  }

  // Check for missing linked work items
  if (!run.requirement_context || !run.requirement_context.has_linked_work_items) {
    items.push({
      id: "linked_work_item",
      title: "Linked Work Item Missing",
      description: "No Jira/Azure work item linked to this PR",
      impact: "Business context and requirements may be incomplete",
      action: "Link a work item to provide complete business context",
      isRequired: false,
      icon: <Users className="w-4 h-4 text-amber-400" />,
      onAction: onLinkWorkItem
    });
  }

  // Check for missing manual tests
  if (!run.manual_tests || run.manual_tests.length === 0) {
    items.push({
      id: "manual_tests",
      title: "Managed Manual Tests Missing",
      description: "No manual test cases defined for this scenario",
      impact: "Manual testing scenarios may not be properly documented",
      action: "Add manual test cases to ensure comprehensive test coverage",
      isRequired: false,
      icon: <TestTube className="w-4 h-4 text-amber-400" />,
      onAction: onAddManualTests
    });
  }

  // Check for missing historical outcomes
  if (!run.historical_outcomes || !run.historical_outcomes.has_relevant_data) {
    items.push({
      id: "historical_outcomes",
      title: "Historical Outcome Memory Unavailable",
      description: "No relevant historical test outcomes available",
      impact: "Recommendations may not benefit from historical learning",
      action: "Historical data will accumulate as more tests are executed",
      isRequired: false,
      icon: <History className="w-4 h-4 text-zinc-400" />,
      onAction: undefined
    });
  }

  return items;
}
