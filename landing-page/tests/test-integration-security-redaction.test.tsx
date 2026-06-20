/**
 * Integration Security Redaction Tests (Phase 7.5A)
 * 
 * Tests for credential redaction in frontend components.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ExecutionSyncDiagnosticsDrawer from '@/components/ExecutionSyncDiagnosticsDrawer';

// Mock global fetch
global.fetch = jest.fn();

describe('ExecutionSyncDiagnosticsDrawer Redaction', () => {
  it('redacts password from request payload', () => {
    const diagnostics = {
      provider: 'TESTRAIL',
      executionId: 'exec-1',
      requestPayload: {
        password: 'secret123',
        username: 'testuser'
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('secret123');
  });

  it('redacts api_key from request payload', () => {
    const diagnostics = {
      provider: 'XRAY',
      executionId: 'exec-1',
      requestPayload: {
        api_key: 'key-123',
        username: 'testuser'
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('key-123');
  });

  it('redacts token from response payload', () => {
    const diagnostics = {
      provider: 'ZEPHYR',
      executionId: 'exec-1',
      requestPayload: {},
      responsePayload: {
        token: 'access-token-xyz',
        status: 'success'
      },
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Response Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('access-token-xyz');
  });

  it('redacts client_secret from nested payload', () => {
    const diagnostics = {
      provider: 'JIRA',
      executionId: 'exec-1',
      requestPayload: {
        config: {
          client_secret: 'secret-abc',
          client_id: 'client-123'
        }
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('secret-abc');
  });

  it('redacts authorization header from payload', () => {
    const diagnostics = {
      provider: 'AZURE_DEVOPS',
      executionId: 'exec-1',
      requestPayload: {
        headers: {
          authorization: 'Bearer token-xyz'
        }
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('Bearer token-xyz');
  });

  it('preserves non-sensitive data in payload', () => {
    const diagnostics = {
      provider: 'TESTRAIL',
      executionId: 'exec-1',
      requestPayload: {
        username: 'testuser',
        project_id: 'PROJ-123',
        test_case_id: 'TC-456'
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('testuser');
    expect(payloadText).toContain('PROJ-123');
    expect(payloadText).toContain('TC-456');
  });

  it('redacts multiple sensitive keys in single payload', () => {
    const diagnostics = {
      provider: 'TESTRAIL',
      executionId: 'exec-1',
      requestPayload: {
        password: 'pass123',
        api_key: 'key-123',
        token: 'token-xyz',
        username: 'testuser'
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('pass123');
    expect(payloadText).not.toContain('key-123');
    expect(payloadText).not.toContain('token-xyz');
    expect(payloadText).toContain('testuser');
  });

  it('redacts from array of objects', () => {
    const diagnostics = {
      provider: 'XRAY',
      executionId: 'exec-1',
      requestPayload: {
        credentials: [
          { api_key: 'key-1', username: 'user1' },
          { password: 'pass-1', username: 'user2' }
        ]
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    expect(payloadText).toContain('***REDACTED***');
    expect(payloadText).not.toContain('key-1');
    expect(payloadText).not.toContain('pass-1');
  });

  it('does not render when closed', () => {
    const diagnostics = {
      provider: 'TESTRAIL',
      executionId: 'exec-1',
      requestPayload: { password: 'secret' },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={false}
        onClose={jest.fn()}
      />
    );

    expect(screen.queryByText('Sync Diagnostics')).not.toBeInTheDocument();
  });

  it('redacts all known sensitive key variants', () => {
    const diagnostics = {
      provider: 'TESTRAIL',
      executionId: 'exec-1',
      requestPayload: {
        password: 'mypassword123',
        api_key: 'mykey123',
        apiKey: 'mykey456',
        token: 'mytoken123',
        client_secret: 'mysecret123',
        clientSecret: 'mysecret456',
        access_token: 'mytoken456',
        accessToken: 'mytoken789',
        refresh_token: 'mytokenabc',
        refreshToken: 'mytokendef',
        authorization: 'myauth123',
        Authorization: 'myauth456',
        secret: 'mysecret789',
        private_key: 'mykey789',
        privateKey: 'mykeyabc'
      },
      responsePayload: {},
      error: null,
      timestamp: '2024-01-01T00:00:00Z'
    };

    render(
      <ExecutionSyncDiagnosticsDrawer
        diagnostics={diagnostics}
        isOpen={true}
        onClose={jest.fn()}
      />
    );

    const payloadText = screen.getByText(/Request Payload/i).parentElement?.textContent || '';
    // All sensitive values should be redacted
    expect(payloadText).not.toContain('mypassword123');
    expect(payloadText).not.toContain('mykey123');
    expect(payloadText).not.toContain('mykey456');
    expect(payloadText).not.toContain('mytoken123');
    expect(payloadText).not.toContain('mysecret123');
    expect(payloadText).not.toContain('mysecret456');
    expect(payloadText).not.toContain('mytoken456');
    expect(payloadText).not.toContain('mytoken789');
    expect(payloadText).not.toContain('mytokenabc');
    expect(payloadText).not.toContain('mytokendef');
    expect(payloadText).not.toContain('myauth123');
    expect(payloadText).not.toContain('myauth456');
    expect(payloadText).not.toContain('mysecret789');
    expect(payloadText).not.toContain('mykey789');
    expect(payloadText).not.toContain('mykeyabc');
  });
});
