"use client";

import React from "react";

interface SafeObjectRendererProps {
  value: any;
  showDebug?: boolean;
  onToggleDebug?: () => void;
}

/**
 * Safe object renderer that prevents raw JSON dumps in production UI.
 * Only shows raw data behind explicit debug mode.
 */
export function SafeObjectRenderer({ 
  value, 
  showDebug = false, 
  onToggleDebug 
}: SafeObjectRendererProps) {
  // Handle null/undefined
  if (value === null || value === undefined) {
    return <span className="text-zinc-400">None</span>;
  }

  // Handle strings
  if (typeof value === "string") {
    return <span className="text-zinc-300">{value}</span>;
  }

  // Handle numbers
  if (typeof value === "number") {
    return <span className="text-zinc-300 font-mono">{value}</span>;
  }

  // Handle booleans
  if (typeof value === "boolean") {
    return <span className="text-zinc-300 font-mono">{value ? "true" : "false"}</span>;
  }

  // Handle arrays
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-zinc-400">None</span>;
    }

    // Special handling for known array types
    if (isMappingArray(value)) {
      return <MappingSummary mappings={value} />;
    }

    if (isEvidenceArray(value)) {
      return <EvidenceSummary evidence={value} />;
    }

    if (isBehaviorArray(value)) {
      return <BehaviorSummary behaviors={value} />;
    }

    // Generic array handling — render items as formatted rows
    if (showDebug) {
      return (
        <div className="space-y-1">
          <span className="text-zinc-500 text-xs">{value.length} items:</span>
          <ul className="list-disc pl-5 text-zinc-300 font-mono space-y-0.5 text-xs max-h-48 overflow-y-auto">
            {value.map((item, idx) => (
              <li key={idx}>
                {typeof item === "object" && item !== null ? (
                  <SafeObjectRenderer value={item} showDebug={true} />
                ) : (
                  <span>{formatNiceLabel(item)}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      );
    }

    return (
      <div className="flex items-center gap-2">
        <span className="text-zinc-300">{value.length} items</span>
        {onToggleDebug && (
          <button
            onClick={onToggleDebug}
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            View details
          </button>
        )}
      </div>
    );
  }

  // Handle objects
  if (typeof value === "object") {
    // Special handling for known object types
    if (isMappingObject(value)) {
      return <MappingDetails mapping={value} />;
    }

    if (isEvidenceObject(value)) {
      return <EvidenceDetails evidence={value} />;
    }

    // If it's a plain object with primitive values, render it as key/value list
    if (isPlainObjectWithPrimitives(value)) {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        return <span className="text-zinc-400">None</span>;
      }
      return (
        <ul className="list-disc pl-5 text-zinc-300 font-mono space-y-0.5">
          {entries.map(([k, v]) => (
            <li key={k}>
              <span className="text-zinc-400">{formatNiceLabel(k)}:</span>{" "}
              <span className="text-zinc-200">{formatNiceLabel(v)}</span>
            </li>
          ))}
        </ul>
      );
    }

    // For objects with nested values, render as recursive key/value rows
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return <span className="text-zinc-400">None</span>;
    }

    if (showDebug) {
      return (
        <div className="space-y-1 text-xs">
          {entries.map(([k, v]) => (
            <div key={k} className="flex flex-col">
              <div className="flex items-start gap-1">
                <span className="text-zinc-400 whitespace-nowrap">{formatNiceLabel(k)}:</span>
                {typeof v !== "object" || v === null ? (
                  <span className="text-zinc-200 font-mono">{formatNiceLabel(v)}</span>
                ) : (
                  <div className="ml-2">
                    <SafeObjectRenderer value={v} showDebug={true} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      );
    }

    // Production mode - show summary for complex nested objects
    const keys = Object.keys(value);
    return (
      <div className="flex items-center gap-2">
        <span className="text-zinc-300">Complex object ({keys.length} fields)</span>
        {onToggleDebug && (
          <button
            onClick={onToggleDebug}
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            View debug details
          </button>
        )}
      </div>
    );
  }

  // Fallback for unknown types
  if (showDebug) {
    return (
      <span className="text-zinc-300 font-mono text-xs">
        {String(value)} (type: {typeof value})
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-zinc-400">Unknown data</span>
      {onToggleDebug && (
        <button
          onClick={onToggleDebug}
          className="text-xs text-blue-400 hover:text-blue-300 underline"
        >
          View debug details
        </button>
      )}
    </div>
  );
}

// Type guards for known data structures
function isMappingArray(arr: any[]): boolean {
  return arr.length > 0 && arr[0] && typeof arr[0] === "object" && (
    "stable_ac_key" in arr[0] || 
    "test_name" in arr[0] || 
    "confidence" in arr[0]
  );
}

function isEvidenceArray(arr: any[]): boolean {
  return arr.length > 0 && arr[0] && (
    typeof arr[0] === "string" ||
    (typeof arr[0] === "object" && "evidence" in arr[0])
  );
}

function isBehaviorArray(arr: any[]): boolean {
  return arr.length > 0 && arr[0] && typeof arr[0] === "object" && (
    "behavior_name" in arr[0] || 
    "title" in arr[0]
  );
}

function isMappingObject(obj: any): boolean {
  return obj && typeof obj === "object" && (
    "stable_ac_key" in obj || 
    "test_name" in obj || 
    "confidence" in obj ||
    "review_status" in obj
  );
}

function isEvidenceObject(obj: any): boolean {
  return obj && typeof obj === "object" && (
    "evidence" in obj || 
    "reason" in obj ||
    "match_reason" in obj
  );
}

function isPlainObjectWithPrimitives(obj: any): boolean {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return false;
  }
  // Check if all values are primitives (string, number, boolean, null, undefined)
  for (const key of Object.keys(obj)) {
    const val = obj[key];
    if (val !== null && typeof val === "object") {
      return false;
    }
  }
  return true;
}

export function formatNiceLabel(val: any): string {
  if (typeof val === "string") {
    // Specific value mappings
    const mappings: Record<string, string> = {
      manual_junit_upload: "manual JUnit upload",
      api_ui: "API/UI",
      test_type_breakdown: "Test type",
      source_breakdown: "Source",
      test_nature_breakdown: "Test nature",
      primary_test_category_breakdown: "Primary test category",
      suite_purpose_breakdown: "Suite purpose",
    };
    if (mappings[val]) return mappings[val];
    
    // Generic fallback: replace _ with space
    let result = val;
    if (result.endsWith("_breakdown")) {
      result = result.slice(0, -10);
    }
    result = result.replace(/_/g, " ");
    
    // Capitalize first letter
    if (result.length > 0) {
      if (val === "manual_junit_upload") {
        return "manual JUnit upload";
      }
      result = result.charAt(0).toUpperCase() + result.slice(1);
    }
    return result;
  }
  return String(val);
}

// Specialized renderers for known types
function MappingSummary({ mappings }: { mappings: any[] }) {
  const total = mappings.length;
  const confirmed = mappings.filter(m => m.review_status === "user_confirmed").length;
  const suggested = mappings.filter(m => m.review_status === "pending_review" || m.review_status === "system_suggested").length;
  const needsReview = mappings.filter(m => m.review_status === "needs_review").length;
  const rejected = mappings.filter(m => m.review_status === "rejected").length;

  return (
    <div className="space-y-1">
      <div className="text-zinc-300">{total} mappings</div>
      <div className="grid grid-cols-2 gap-1 text-xs">
        <div className="text-green-400">✓ {confirmed} confirmed</div>
        <div className="text-blue-400">→ {suggested} suggested</div>
        <div className="text-orange-400">⚠ {needsReview} needs review</div>
        <div className="text-red-400">✗ {rejected} rejected</div>
      </div>
    </div>
  );
}

function MappingDetails({ mapping }: { mapping: any }) {
  return (
    <div className="space-y-1 text-xs">
      {mapping.stable_ac_key && (
        <div><span className="text-zinc-500">AC:</span> {mapping.stable_ac_key}</div>
      )}
      {mapping.test_name && (
        <div><span className="text-zinc-500">Test:</span> {mapping.test_name}</div>
      )}
      {mapping.confidence_score !== undefined && mapping.confidence_score !== null && (
        <div><span className="text-zinc-500">Confidence:</span> {Math.round(mapping.confidence_score * 100)}%</div>
      )}
      {mapping.confidence_label && (
        <div><span className="text-zinc-500">Confidence:</span> {mapping.confidence_label}</div>
      )}
      {mapping.review_status && (
        <div><span className="text-zinc-500">Status:</span> {mapping.review_status.replace(/_/g, " ")}</div>
      )}
    </div>
  );
}

function EvidenceSummary({ evidence }: { evidence: string[] | any[] }) {
  const count = evidence.length;
  return (
    <div className="space-y-1">
      <div className="text-zinc-300">{count} evidence items</div>
      {count > 0 && count <= 3 && (
        <ul className="text-xs text-zinc-400 space-y-0.5">
          {evidence.slice(0, 3).map((item, idx) => (
            <li key={idx}>• {typeof item === "string" ? item : JSON.stringify(item)}</li>
          ))}
        </ul>
      )}
      {count > 3 && (
        <div className="text-xs text-zinc-400">
          Showing 3 of {count} items...
        </div>
      )}
    </div>
  );
}

function EvidenceDetails({ evidence }: { evidence: any }) {
  return (
    <div className="space-y-1 text-xs">
      {evidence.reason && (
        <div><span className="text-zinc-500">Reason:</span> {evidence.reason}</div>
      )}
      {evidence.match_reason && (
        <div><span className="text-zinc-500">Match:</span> {evidence.match_reason.replace(/_/g, " ")}</div>
      )}
      {evidence.confidence_score !== undefined && evidence.confidence_score !== null && (
        <div><span className="text-zinc-500">Confidence:</span> {Math.round(evidence.confidence_score * 100)}%</div>
      )}
      {evidence.confidence_label && (
        <div><span className="text-zinc-500">Confidence:</span> {evidence.confidence_label}</div>
      )}
      {evidence.evidence && Array.isArray(evidence.evidence) && (
        <div className="space-y-1">
          <div className="text-zinc-500">Evidence:</div>
          <ul className="pl-3 space-y-0.5">
            {evidence.evidence.slice(0, 3).map((item: any, idx: number) => (
              <li key={idx} className="text-zinc-400">• {typeof item === "string" ? item : JSON.stringify(item)}</li>
            ))}
            {evidence.evidence.length > 3 && (
              <li className="text-zinc-500">... and {evidence.evidence.length - 3} more</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function BehaviorSummary({ behaviors }: { behaviors: any[] }) {
  return (
    <div className="space-y-1">
      <div className="text-zinc-300">{behaviors.length} behaviors</div>
      <ul className="text-xs text-zinc-400 space-y-0.5">
        {behaviors.slice(0, 3).map((behavior, idx) => (
          <li key={idx}>• {behavior.behavior_name || behavior.title || behavior.name || "Unknown behavior"}</li>
        ))}
        {behaviors.length > 3 && (
          <li className="text-zinc-500">... and {behaviors.length - 3} more</li>
        )}
      </ul>
    </div>
  );
}
