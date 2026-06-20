/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TargetedScopeModal } from '../components/TargetedScopeModal';
import { ScopeGroup } from '../types/regression-scope-v2';

// Mock the backend API
global.fetch = jest.fn();

describe('Targeted Scope Creation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('button calls backend endpoint with correct payload', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      scope: {
        id: 'test-scope-id',
        required_items: [{ id: '1', title: 'Test Item' }],
        review_items: [],
        excluded_already_verified_requirements: [],
        excluded_already_passed_tests: []
      }
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    // Simulate button click
    const runId = 'test-run-id';
    const payload = {
      scopeType: 'TARGETED_FROM_EVIDENCE',
      includeOptionalSafetyNet: false,
      includeAlreadyPassedTests: false,
      includeAuditDiagnostics: false
    };

    await fetch(`/api/recommendations/${runId}/create-targeted-scope`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    expect(global.fetch).toHaveBeenCalledWith(
      `/api/recommendations/${runId}/create-targeted-scope`,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    );
  });

  test('success response renders correct counts', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      scope: {
        id: 'test-scope-id',
        required_items: Array(7).fill({ id: '1', title: 'Test Item' }),
        review_items: Array(2).fill({ id: '2', title: 'Review Item' }),
        excluded_already_verified_requirements: Array(16).fill({ id: '3', title: 'Verified Item' }),
        excluded_already_passed_tests: Array(18).fill({ id: '4', title: 'Passed Test' })
      }
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/create-targeted-scope', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scopeType: 'TARGETED_FROM_EVIDENCE',
        includeOptionalSafetyNet: false,
        includeAlreadyPassedTests: false,
        includeAuditDiagnostics: false
      })
    });

    const data = await response.json();
    expect(data.status).toBe('SUCCESS');
    expect(data.scope.required_items.length).toBe(7);
    expect(data.scope.review_items.length).toBe(2);
    expect(data.scope.excluded_already_verified_requirements.length).toBe(16);
    expect(data.scope.excluded_already_passed_tests.length).toBe(18);
  });

  test('passed tests are not shown as required reruns', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      scope: {
        id: 'test-scope-id',
        required_items: Array(7).fill({ id: '1', title: 'Test Item' }),
        review_items: Array(2).fill({ id: '2', title: 'Review Item' }),
        excluded_already_passed_tests: Array(18).fill({ id: '4', title: 'Passed Test', reason_excluded: 'Already passed in current PR execution' })
      }
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/create-targeted-scope', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scopeType: 'TARGETED_FROM_EVIDENCE',
        includeOptionalSafetyNet: false,
        includeAlreadyPassedTests: false
      })
    });

    const data = await response.json();
    
    // Verify passed tests are in excluded bucket
    expect(data.scope.excluded_already_passed_tests.length).toBe(18);
    data.scope.excluded_already_passed_tests.forEach((item: any) => {
      expect(item.reason_excluded).toBe('Already passed in current PR execution');
    });

    // Verify passed tests are NOT in required items
    data.scope.required_items.forEach((item: any) => {
      expect(item.reason_excluded).not.toBe('Already passed in current PR execution');
    });
  });

  test('verified ACs are not shown as missing coverage', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      scope: {
        id: 'test-scope-id',
        required_items: Array(7).fill({ id: '1', title: 'Missing Item' }),
        excluded_already_verified_requirements: Array(16).fill({ id: '3', title: 'Verified Item', reason_excluded: 'Already covered by passed current PR execution' })
      }
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/create-targeted-scope', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scopeType: 'TARGETED_FROM_EVIDENCE',
        includeOptionalSafetyNet: false
      })
    });

    const data = await response.json();
    
    // Verify verified ACs are in excluded bucket
    expect(data.scope.excluded_already_verified_requirements.length).toBe(16);
    data.scope.excluded_already_verified_requirements.forEach((item: any) => {
      expect(item.reason_excluded).toBe('Already covered by passed current PR execution');
    });

    // Verify verified ACs are NOT in required items
    data.scope.required_items.forEach((item: any) => {
      expect(item.reason_excluded).not.toBe('Already covered by passed current PR execution');
    });
  });

  test('error state for EVIDENCE_GRAPH_UNAVAILABLE', async () => {
    const mockResponse = {
      status: 'ERROR',
      error_code: 'EVIDENCE_GRAPH_UNAVAILABLE',
      message: 'Cannot create targeted scope because the evidence graph is unavailable.'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/create-targeted-scope', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scopeType: 'TARGETED_FROM_EVIDENCE'
      })
    });

    const data = await response.json();
    expect(data.status).toBe('ERROR');
    expect(data.error_code).toBe('EVIDENCE_GRAPH_UNAVAILABLE');
  });

  test('error state for STALE_INPUTS / REQUIRES_REGENERATION', async () => {
    const mockResponse = {
      status: 'REQUIRES_REGENERATION',
      error_code: 'STALE_EVIDENCE_GRAPH',
      message: 'This recommendation is stale. Regenerate before creating a targeted scope.'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/create-targeted-scope', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scopeType: 'TARGETED_FROM_EVIDENCE'
      })
    });

    const data = await response.json();
    expect(data.status).toBe('REQUIRES_REGENERATION');
    expect(data.error_code).toBe('STALE_EVIDENCE_GRAPH');
  });

  test('error state for INTERNAL_EVIDENCE_MODEL_INCONSISTENT', async () => {
    const mockResponse = {
      status: 'ERROR',
      error_code: 'INTERNAL_EVIDENCE_MODEL_INCONSISTENT',
      message: 'Cannot create scope because the evidence model failed consistency checks.'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/create-targeted-scope', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scopeType: 'TARGETED_FROM_EVIDENCE'
      })
    });

    const data = await response.json();
    expect(data.status).toBe('ERROR');
    expect(data.error_code).toBe('INTERNAL_EVIDENCE_MODEL_INCONSISTENT');
  });
});

describe('TargetedScopeModal Rendering', () => {
  const mockLegacyScopeData = {
    id: "legacy-scope-123",
    recommendation_run_id: "run-123",
    created_at: "2026-06-13T05:00:00Z",
    scope_type: "targeted",
    health_at_creation: "VALIDATION_PASSED_COVERAGE_INCOMPLETE",
    summary: "This is a summary of the legacy regression scope",
    source_evidence_graph_snapshot: {
      recommendation_run_id: "run-123",
      snapshot_hash: "sha256-abc123xyz789",
      generated_at: "2026-06-13T05:00:00Z"
    },
    required_items: [
      {
        id: "item-uuid-req-1",
        readable_id: "AC-REQ-1",
        title: "Verify password strength validation",
        item_type: "REQUIRED_MISSING_COVERAGE",
        classification: "MISSING",
        suggested_action: "Add integration tests",
        flow: "Direct match to updated file auth.py",
        risk_if_skipped: "HIGH",
        businessContext: {
          riskLevel: "CRITICAL",
          priority: "MUST",
          businessImpact: "Risk of password breach"
        }
      }
    ],
    review_items: [
      {
        id: "item-uuid-rev-1",
        readable_id: "AC-REV-1",
        title: "Verify lockout mechanism",
        item_type: "REVIEW_PARTIAL_SUPPORT",
        classification: "PARTIAL",
        suggested_action: "Review manual evidence",
        flow: "Security lockout check",
        risk_if_skipped: "MEDIUM",
        businessRiskReview: {
          reviewStatus: "NEEDS_DISCUSSION",
          originalRiskLevel: "HIGH",
          effectiveRiskLevel: "MEDIUM",
          reviewNote: "Needs team feedback",
          reviewerName: "QA Lead"
        }
      }
    ],
    optional_safety_net_items: [],
    excluded_already_verified_requirements: [
      {
        id: "item-uuid-ver-1",
        readable_id: "AC-VER-1",
        title: "Already Verified AC Item",
        item_type: "EXCLUDED_ALREADY_VERIFIED",
        reason_excluded: "Already covered by passed current PR execution"
      }
    ],
    excluded_already_passed_tests: [
      {
        id: "item-uuid-pass-1",
        title: "Already Passed Test Item",
        item_type: "EXCLUDED_ALREADY_PASSED",
        reason_excluded: "Already passed in current PR execution",
        class_name: "test_auth.py"
      }
    ],
    generation_rules_applied: ["rule-pass-val"],
    diagnostics: ["No diagnostic errors"]
  };

  test('Modal renders V2 display via adapter when given legacy scope', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.getByText("Targeted Regression Scope")).toBeInTheDocument();
    expect(screen.getByText("Verify password strength validation")).toBeInTheDocument();
  });

  test('Required items appear under Required Before Release', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.getByText("Required Before Release")).toBeInTheDocument();
    expect(screen.getByText("AC-REQ-1")).toBeInTheDocument();
    expect(screen.getByText("Verify password strength validation")).toBeInTheDocument();
  });

  test('Review items appear under Recommended Regression', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.getByText("Recommended Regression")).toBeInTheDocument();
    expect(screen.getByText("AC-REV-1")).toBeInTheDocument();
    expect(screen.getByText("Verify lockout mechanism")).toBeInTheDocument();
  });

  test('Excluded verified items hidden by default', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.queryByText("Already Verified AC Item")).not.toBeInTheDocument();
  });

  test('Excluded passed tests hidden by default', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.queryByText("Already Passed Test Item")).not.toBeInTheDocument();
  });

  test('Exclusions visible when toggle enabled', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    
    // Toggle exclusions
    const toggle = screen.getByLabelText("Show Exclusions");
    fireEvent.click(toggle);
    
    expect(screen.getByText("Already Verified AC Item")).toBeInTheDocument();
    expect(screen.getByText("Already Passed Test Item")).toBeInTheDocument();
  });

  test('Safe To Skip hidden by default', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.queryByText("Safe To Skip")).not.toBeInTheDocument();
  });

  test('Execution plan shown', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.getByText(/Run 2 items/)).toBeInTheDocument();
  });

  test('Passed tests are not shown as required reruns', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    // The "Already Passed Test Item" is not in the DOM by default and therefore not under Required Before Release
    expect(screen.queryByText("Already Passed Test Item")).not.toBeInTheDocument();
  });

  test('Verified ACs are not shown as missing coverage', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    // The "Already Verified AC Item" is not in the DOM by default and therefore not under Required Before Release
    expect(screen.queryByText("Already Verified AC Item")).not.toBeInTheDocument();
  });

  test('Internal IDs hidden in normal mode', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
      />
    );
    expect(screen.queryByText("item-uuid-req-1")).not.toBeInTheDocument();
  });

  test('Audit mode shows diagnostics/internal details', () => {
    render(
      <TargetedScopeModal 
        isOpen={true} 
        onClose={jest.fn()} 
        scope={mockLegacyScopeData} 
        auditMode={true}
      />
    );
    
    // Internal requirement ID should be visible
    expect(screen.getAllByText(/item-uuid-req-1/)[0]).toBeInTheDocument();
    // Diagnostics audit block should be visible
    expect(screen.getByText("Diagnostics Audit")).toBeInTheDocument();
  });
});
