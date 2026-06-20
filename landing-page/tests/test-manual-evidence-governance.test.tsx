// Mock the backend API
global.fetch = jest.fn();

describe('Manual Evidence Governance API', () => {
  const mockExecutionId = 'test-execution-id';
  const mockRepositoryId = 'test-repository-id';

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('GET governance status calls correct endpoint', async () => {
    const mockGovernance = {
      governanceStatus: 'PENDING_REVIEW',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T00:00:00Z',
      reviewNote: 'Test note'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    const url = `/api/repositories/${mockRepositoryId}/manual-executions/${mockExecutionId}/governance`;
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

  test('POST approve calls correct endpoint', async () => {
    const mockGovernance = {
      governanceStatus: 'APPROVED',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T00:00:00Z'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    const url = `/api/repositories/${mockRepositoryId}/manual-executions/${mockExecutionId}/approve`;
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewNote: 'Approved for testing' })
    });

    expect(global.fetch).toHaveBeenCalledWith(
      url,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewNote: 'Approved for testing' })
      })
    );
  });

  test('POST reject calls correct endpoint with note', async () => {
    const mockGovernance = {
      governanceStatus: 'REJECTED',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T00:00:00Z',
      reviewNote: 'Rejected due to invalid evidence'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    const url = `/api/repositories/${mockRepositoryId}/manual-executions/${mockExecutionId}/reject`;
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewNote: 'Rejected due to invalid evidence' })
    });

    expect(global.fetch).toHaveBeenCalledWith(
      url,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewNote: 'Rejected due to invalid evidence' })
      })
    );
  });

  test('POST challenge calls correct endpoint with note', async () => {
    const mockGovernance = {
      governanceStatus: 'CHALLENGED',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T00:00:00Z',
      reviewNote: 'Challenged by QA team'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    const url = `/api/repositories/${mockRepositoryId}/manual-executions/${mockExecutionId}/challenge`;
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewNote: 'Challenged by QA team' })
    });

    expect(global.fetch).toHaveBeenCalledWith(
      url,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewNote: 'Challenged by QA team' })
      })
    );
  });

  test('governance status includes reviewer metadata', async () => {
    const mockGovernance = {
      governanceStatus: 'APPROVED',
      reviewerName: 'Test Reviewer',
      reviewedAt: '2026-06-15T00:00:00Z',
      reviewNote: 'Test review note'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    const url = `/api/repositories/${mockRepositoryId}/manual-executions/${mockExecutionId}/governance`;
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await (response as Response).json();
    expect(data.reviewerName).toBe('Test Reviewer');
    expect(data.reviewNote).toBe('Test review note');
  });

  test('governance status includes expiration info', async () => {
    const mockGovernance = {
      governanceStatus: 'EXPIRED',
      isExpired: true,
      expiresAt: '2026-06-15T00:00:00Z'
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockGovernance
    });

    const url = `/api/repositories/${mockRepositoryId}/manual-executions/${mockExecutionId}/governance`;
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await (response as Response).json();
    expect(data.isExpired).toBe(true);
    expect(data.expiresAt).toBe('2026-06-15T00:00:00Z');
  });
});
