"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Copy, Eye, EyeOff, Trash2, Plus, AlertTriangle } from 'lucide-react';

interface CIToken {
  id: string;
  name: string;
  scopes: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface CreateTokenResponse {
  id: string;
  repositoryId: string;
  name: string;
  scopes: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
  raw_token: string;
}

export default function CITokensPage({ params }: { params: { repositoryId: string } }) {
  const [tokens, setTokens] = useState<CIToken[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [newTokenRaw, setNewTokenRaw] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTokens();
  }, [params.repositoryId]);

  const loadTokens = async () => {
    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/ci-tokens`);
      if (!response.ok) throw new Error('Failed to load tokens');
      const data = await response.json();
      setTokens(data.tokens || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tokens');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateToken = async () => {
    if (!newTokenName.trim()) return;

    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/ci-tokens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTokenName, scopes: 'pipeline:trigger,artifact:read' }),
      });

      if (!response.ok) throw new Error('Failed to create token');

      const data: CreateTokenResponse = await response.json();
      setNewTokenRaw(data.raw_token);
      setShowCreateModal(false);
      setNewTokenName('');
      loadTokens();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create token');
    }
  };

  const handleRevokeToken = async (tokenId: string) => {
    if (!confirm('Are you sure you want to revoke this token? This action cannot be undone.')) return;

    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/ci-tokens/${tokenId}/revoke`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Failed to revoke token');
      loadTokens();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke token');
    }
  };

  const handleCopyToken = () => {
    if (newTokenRaw) {
      navigator.clipboard.writeText(newTokenRaw);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDismissRawToken = () => {
    setNewTokenRaw(null);
  };

  if (loading) {
    return <div className="p-6">Loading...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">CI Tokens</h1>
          <p className="text-muted-foreground">Manage CI/CD pipeline tokens for this repository</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Create Token
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {newTokenRaw && (
        <Alert className="border-yellow-500 bg-yellow-50">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800">
            <div className="flex flex-col space-y-2">
              <p className="font-semibold">Copy this token now. You will not be able to view it again.</p>
              <div className="flex items-center space-x-2">
                <Input value={newTokenRaw} readOnly className="font-mono text-sm" />
                <Button onClick={handleCopyToken} variant="outline" size="sm">
                  <Copy className="w-4 h-4 mr-2" />
                  {copied ? 'Copied!' : 'Copy'}
                </Button>
                <Button onClick={handleDismissRawToken} variant="outline" size="sm">
                  Dismiss
                </Button>
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Active Tokens</CardTitle>
          <CardDescription>Tokens that can be used to trigger pipelines and access artifacts</CardDescription>
        </CardHeader>
        <CardContent>
          {tokens.length === 0 ? (
            <p className="text-muted-foreground py-4">No CI tokens found. Create one to get started.</p>
          ) : (
            <div className="space-y-4">
              {tokens.map((token) => (
                <div key={token.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <h3 className="font-semibold">{token.name}</h3>
                      <Badge variant={token.is_active ? 'default' : 'secondary'}>
                        {token.is_active ? 'Active' : 'Revoked'}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">Scopes: {token.scopes}</p>
                    <p className="text-xs text-muted-foreground">
                      Created: {new Date(token.created_at).toLocaleString()}
                      {token.last_used_at && ` • Last used: ${new Date(token.last_used_at).toLocaleString()}`}
                    </p>
                  </div>
                  {token.is_active && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleRevokeToken(token.id)}
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      Revoke
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Create CI Token</CardTitle>
              <CardDescription>Create a new token for CI/CD pipeline authentication</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="token-name">Token Name</Label>
                <Input
                  id="token-name"
                  value={newTokenName}
                  onChange={(e) => setNewTokenName(e.target.value)}
                  placeholder="e.g., GitHub Actions Token"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreateToken} disabled={!newTokenName.trim()}>
                  Create Token
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
