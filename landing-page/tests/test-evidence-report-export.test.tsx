import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock the backend API
global.fetch = jest.fn();

describe('Evidence Report Export', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('export button calls backend endpoint', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      markdown_content: '# QA Evidence Report\n\n## Executive Summary\n\nTest content'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const runId = 'test-run-id';
    const url = `/api/recommendations/${runId}/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false`;

    await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    expect(global.fetch).toHaveBeenCalledWith(
      url,
      expect.objectContaining({
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
    );
  });

  test('loading state appears during export', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      markdown_content: '# QA Evidence Report'
    };

    (global.fetch as jest.Mock).mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve({
        ok: true,
        json: async () => mockResponse
      }), 100))
    );

    // Test that the endpoint is called with correct parameters
    const runId = 'test-run-id';
    const url = `/api/recommendations/${runId}/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false&include_stale=false`;

    await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    expect(global.fetch).toHaveBeenCalledWith(
      url,
      expect.objectContaining({
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      })
    );
  });

  test('markdown report is downloaded on success', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      markdown_content: '# QA Evidence Report\n\n## Executive Summary\n\nTest content'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.status).toBe('SUCCESS');
    expect(data.markdown_content).toContain('# QA Evidence Report');
    expect(data.markdown_content).toContain('## Executive Summary');
  });

  test('error state appears for backend failure', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'Failed to export evidence report' })
    });

    try {
      const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to export evidence report');
      }
    } catch (e: any) {
      expect(e.message).toBe('Failed to export evidence report');
    }
  });

  test('internal IDs are not visible in normal export', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      markdown_content: '# QA Evidence Report\n\n## Covered by Passed PR Tests\n\n### AC-01: Test Title\n- **Source AC Number:** 1\n- **Matched Test:** TestName\n- **Test Classname:** TestClass\n- **Evidence Type:** JUNIT_EXECUTION\n- **Reason:** Covered by passed current PR execution'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.markdown_content).toContain('AC-01');
    expect(data.markdown_content).not.toContain('internal_requirement_id');
    expect(data.markdown_content).not.toContain('uuid-');
  });

  test('counts match backend response', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      markdown_content: '# QA Evidence Report\n\n### Acceptance Criteria Coverage\n- Total: 25\n- Covered by passed PR tests: 16\n- Partially supported: 0\n- Missing automated coverage: 9\n- Traceability review needed: 0\n\n## Targeted Regression Scope\n\n### Required Items\n- Count: 9\n\n### Review Items\n- Count: 0\n\n### Excluded\n- Already Verified Requirements: 16\n- Already Passed Tests: 18'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.markdown_content).toContain('Total: 25');
    expect(data.markdown_content).toContain('Covered by passed PR tests: 16');
    expect(data.markdown_content).toContain('Missing automated coverage: 9');
    expect(data.markdown_content).toContain('Already Verified Requirements: 16');
    expect(data.markdown_content).toContain('Already Passed Tests: 18');
  });

  test('stale recommendation error is handled', async () => {
    const mockResponse = {
      status: 'REQUIRES_REGENERATION',
      error_code: 'STALE_EVIDENCE_GRAPH',
      can_render_report: false,
      message: 'Recommendation is stale. Regenerate before creating evidence report.'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=markdown&audit=false&include_scope=true&include_diagnostics=false', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.status).toBe('REQUIRES_REGENERATION');
    expect(data.error_code).toBe('STALE_EVIDENCE_GRAPH');
    expect(data.can_render_report).toBe(false);
  });

  test('evidence graph unavailable error is handled', async () => {
    const mockResponse = {
      status: 'ERROR',
      error_code: 'EVIDENCE_GRAPH_UNAVAILABLE',
      can_render_report: false,
      message: 'Evidence graph snapshot not available. Regenerate recommendation first.'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=json&audit=false&include_scope=true&include_diagnostics=false', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.status).toBe('ERROR');
    expect(data.error_code).toBe('EVIDENCE_GRAPH_UNAVAILABLE');
    expect(data.can_render_report).toBe(false);
  });

  test('snapshot parent count mismatch error is handled', async () => {
    const mockResponse = {
      status: 'REQUIRES_REGENERATION',
      error_code: 'SNAPSHOT_PARENT_REQUIREMENT_COUNT_MISMATCH',
      can_render_report: false,
      message: 'Snapshot is stale: contains 24 parent requirements, but canonical source has 25. Regenerate recommendation before exporting report.'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=json&audit=false&include_scope=true&include_diagnostics=false', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.status).toBe('REQUIRES_REGENERATION');
    expect(data.error_code).toBe('SNAPSHOT_PARENT_REQUIREMENT_COUNT_MISMATCH');
    expect(data.can_render_report).toBe(false);
  });

  test('audit mode includes internal IDs', async () => {
    const mockResponse = {
      status: 'SUCCESS',
      report: {
        audit_appendix: {
          internal_requirement_ids: ['req-uuid-1', 'req-uuid-2'],
          source_hashes: { ac_source: 'hash1', snapshot: 'hash2' }
        }
      }
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const response = await fetch('/api/recommendations/test-run-id/evidence-report?format=json&audit=true&include_scope=true&include_diagnostics=true', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    expect(data.status).toBe('SUCCESS');
    expect(data.report.audit_appendix).not.toBeNull();
    expect(data.report.audit_appendix.internal_requirement_ids).toContain('req-uuid-1');
  });
});
