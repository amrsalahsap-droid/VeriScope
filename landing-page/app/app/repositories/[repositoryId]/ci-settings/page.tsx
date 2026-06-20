"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Info, AlertTriangle, Settings, Shield, GitBranch } from 'lucide-react';

interface CICDPolicy {
  id: string;
  repository_id: string;
  enabled: boolean;
  required_check_name: string;
  ci_fail_on_partial: boolean;
  fail_on_unknown_gate: boolean;
  fail_on_missing_recommendation: boolean;
  require_artifact: boolean;
  require_pr_comment: boolean;
  allow_manual_override: boolean;
  manual_override_requires_reason: boolean;
  strict_mode: boolean;
  created_at: string;
  updated_at: string;
  updated_by: string | null;
}

interface BranchProtectionReadiness {
  repository_id: string;
  required_check_name: string;
  github_app_installed: boolean;
  checks_write_permission: boolean;
  statuses_write_permission: boolean;
  pr_comment_permission: boolean;
  workflow_configured: boolean;
  latest_successful_pipeline_run: string | null;
  latest_github_status_result: string | null;
  latest_artifact_available: boolean;
  policy_strictness: string;
  recommended_branch_protection: string;
  is_ready: boolean;
  readiness_issues: string[];
}

interface PolicyPreviewResponse {
  githubConclusion: string;
  wouldBlockPr: boolean;
  qualityGate: string;
  reason: string;
  rulesApplied: string[];
}

interface PresetDefinition {
  name: string;
  definition: {
    name: string;
    description: string;
    risk_level: string;
    recommended_use_case: string;
    settings: Record<string, any>;
    impact: Record<string, string>;
  };
}

interface EffectivePolicyResponse {
  effective_policy: Record<string, any>;
  source: string;
  source_preset: string | null;
  organization_default_preset: string | null;
  repository_override_exists: boolean;
  drift_from_default: boolean;
  drift_fields: string[];
}

interface PolicyDriftResponse {
  drift_detected: boolean;
  drift_fields: string[];
  default_values: Record<string, any>;
  repository_values: Record<string, any>;
  risk_level: string;
  recommended_action: string;
}

interface PresetRecommendationResponse {
  recommended_preset: string;
  confidence: string;
  reasons: string[];
  risk_signals: string[];
  tradeoffs: string[];
}

export default function CISettingsPage({ params }: { params: { repositoryId: string } }) {
  const [policy, setPolicy] = useState<CICDPolicy | null>(null);
  const [readiness, setReadiness] = useState<BranchProtectionReadiness | null>(null);
  const [previewResult, setPreviewResult] = useState<PolicyPreviewResponse | null>(null);
  const [previewScenario, setPreviewScenario] = useState({
    releaseDecision: 'Partially Verified',
    recommendationHealth: 'Ready',
    qualityGate: 'PARTIAL',
    hasRecommendationRun: true,
    hasArtifact: true,
    hasPrComment: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Governance state
  const [presets, setPresets] = useState<PresetDefinition[]>([]);
  const [effectivePolicy, setEffectivePolicy] = useState<EffectivePolicyResponse | null>(null);
  const [policyDrift, setPolicyDrift] = useState<PolicyDriftResponse | null>(null);
  const [presetRecommendation, setPresetRecommendation] = useState<PresetRecommendationResponse | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [governanceLoading, setGovernanceLoading] = useState(false);

  useEffect(() => {
    loadPolicy();
    loadReadiness();
    loadGovernanceData();
  }, [params.repositoryId]);

  const loadPolicy = async () => {
    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy`);
      if (!response.ok) throw new Error('Failed to load CI/CD policy');
      const data = await response.json();
      setPolicy(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load policy');
    } finally {
      setLoading(false);
    }
  };

  const loadReadiness = async () => {
    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/branch-protection-readiness`);
      if (!response.ok) throw new Error('Failed to load branch protection readiness');
      const data = await response.json();
      setReadiness(data);
    } catch (err) {
      console.error('Failed to load readiness:', err);
    }
  };

  const loadGovernanceData = async () => {
    setGovernanceLoading(true);
    try {
      // Load presets
      const presetsResponse = await fetch('/api/repositories/cicd/policy/presets');
      if (presetsResponse.ok) {
        const presetsData = await presetsResponse.json();
        setPresets(presetsData.presets);
      }

      // Load effective policy
      const effectiveResponse = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/effective`);
      if (effectiveResponse.ok) {
        const effectiveData = await effectiveResponse.json();
        setEffectivePolicy(effectiveData);
        setSelectedPreset(effectiveData.source_preset);
      }

      // Load policy drift
      const driftResponse = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/drift`);
      if (driftResponse.ok) {
        const driftData = await driftResponse.json();
        setPolicyDrift(driftData);
      }

      // Load preset recommendation
      const recommendationResponse = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/recommend-preset`, {
        method: 'POST'
      });
      if (recommendationResponse.ok) {
        const recommendationData = await recommendationResponse.json();
        setPresetRecommendation(recommendationData);
      }
    } catch (err) {
      console.error('Failed to load governance data:', err);
    } finally {
      setGovernanceLoading(false);
    }
  };

  const handleApplyPreset = async (presetName: string) => {
    setSaving(true);
    setError(null);

    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/apply-preset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset_name: presetName, reason: 'Applied via UI' }),
      });

      if (!response.ok) throw new Error('Failed to apply preset');

      await loadPolicy();
      await loadGovernanceData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply preset');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdatePolicy = async (updates: Partial<CICDPolicy>) => {
    setSaving(true);
    setError(null);

    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });

      if (!response.ok) throw new Error('Failed to update policy');

      const data = await response.json();
      setPolicy(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update policy');
    } finally {
      setSaving(false);
    }
  };

  const handlePreviewPolicy = async () => {
    setPreviewing(true);
    setError(null);

    try {
      const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(previewScenario),
      });

      if (!response.ok) throw new Error('Failed to preview policy');

      const data = await response.json();
      setPreviewResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview policy');
    } finally {
      setPreviewing(false);
    }
  };

  if (loading) {
    return <div className="p-6">Loading...</div>;
  }

  if (!policy) {
    return <div className="p-6">Failed to load policy</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">CI/CD Policy</h1>
        <p className="text-muted-foreground">Configure quality gate policies and branch protection for this repository</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="policy" className="space-y-6">
        <TabsList>
          <TabsTrigger value="policy">
            <Settings className="w-4 h-4 mr-2" />
            Policy Settings
          </TabsTrigger>
          <TabsTrigger value="governance">
            <Shield className="w-4 h-4 mr-2" />
            Governance
          </TabsTrigger>
          <TabsTrigger value="preview">
            <Shield className="w-4 h-4 mr-2" />
            Policy Preview
          </TabsTrigger>
          <TabsTrigger value="branch-protection">
            <GitBranch className="w-4 h-4 mr-2" />
            Branch Protection
          </TabsTrigger>
        </TabsList>

        <TabsContent value="policy" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Policy Enablement</CardTitle>
              <CardDescription>Enable or disable Veriscope CI/CD policy for this repository</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="enabled" className="text-base font-semibold">
                    Enable Veriscope CI Gate
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When disabled, Veriscope will not publish GitHub statuses or enforce quality gates.
                  </p>
                </div>
                <Switch
                  id="enabled"
                  checked={policy.enabled}
                  onCheckedChange={(value) => handleUpdatePolicy({ enabled: value })}
                  disabled={saving}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>GitHub Check Configuration</CardTitle>
              <CardDescription>Configure the GitHub check name used for branch protection</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="required_check_name" className="text-base font-semibold">
                  Required Check Name
                </Label>
                <Input
                  id="required_check_name"
                  value={policy.required_check_name}
                  onChange={(e) => handleUpdatePolicy({ required_check_name: e.target.value })}
                  disabled={saving}
                  placeholder="Veriscope Quality Gate"
                />
                <p className="text-sm text-muted-foreground">
                  This is the check name that should be required in GitHub branch protection rules.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quality Gate Behavior</CardTitle>
              <CardDescription>Configure how quality gate results affect CI status</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="ci_fail_on_partial" className="text-base font-semibold">
                    Fail CI when Quality Gate is Partial
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When disabled, PARTIAL results publish a neutral GitHub status.
                    When enabled, PARTIAL results fail the GitHub check.
                  </p>
                </div>
                <Switch
                  id="ci_fail_on_partial"
                  checked={policy.ci_fail_on_partial}
                  onCheckedChange={(value) => handleUpdatePolicy({ ci_fail_on_partial: value })}
                  disabled={saving}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="fail_on_unknown_gate" className="text-base font-semibold">
                    Fail CI when Quality Gate is Unknown
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When disabled, UNKNOWN results publish a neutral GitHub status.
                    When enabled, UNKNOWN results fail the GitHub check.
                  </p>
                </div>
                <Switch
                  id="fail_on_unknown_gate"
                  checked={policy.fail_on_unknown_gate}
                  onCheckedChange={(value) => handleUpdatePolicy({ fail_on_unknown_gate: value })}
                  disabled={saving}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="fail_on_missing_recommendation" className="text-base font-semibold">
                    Fail CI when Recommendation is Missing
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When disabled, missing recommendations publish a neutral GitHub status.
                    When enabled, missing recommendations fail the GitHub check.
                  </p>
                </div>
                <Switch
                  id="fail_on_missing_recommendation"
                  checked={policy.fail_on_missing_recommendation}
                  onCheckedChange={(value) => handleUpdatePolicy({ fail_on_missing_recommendation: value })}
                  disabled={saving}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="strict_mode" className="text-base font-semibold">
                    Strict Mode
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When enabled, both PARTIAL and UNKNOWN quality gates will fail the GitHub check.
                    This overrides individual fail_on_partial and fail_on_unknown_gate settings.
                  </p>
                </div>
                <Switch
                  id="strict_mode"
                  checked={policy.strict_mode}
                  onCheckedChange={(value) => handleUpdatePolicy({ strict_mode: value })}
                  disabled={saving}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Artifact and Comment Requirements</CardTitle>
              <CardDescription>Configure requirements for artifacts and PR comments</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="require_artifact" className="text-base font-semibold">
                    Require Artifact
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When enabled, pipeline runs require artifact generation for completion.
                  </p>
                </div>
                <Switch
                  id="require_artifact"
                  checked={policy.require_artifact}
                  onCheckedChange={(value) => handleUpdatePolicy({ require_artifact: value })}
                  disabled={saving}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="require_pr_comment" className="text-base font-semibold">
                    Require PR Comment
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When enabled, pipeline runs require PR comment creation for completion.
                  </p>
                </div>
                <Switch
                  id="require_pr_comment"
                  checked={policy.require_pr_comment}
                  onCheckedChange={(value) => handleUpdatePolicy({ require_pr_comment: value })}
                  disabled={saving}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Manual Override</CardTitle>
              <CardDescription>Configure manual override permissions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="allow_manual_override" className="text-base font-semibold">
                    Allow Manual Override
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When enabled, authorized users can manually override quality gate decisions.
                  </p>
                </div>
                <Switch
                  id="allow_manual_override"
                  checked={policy.allow_manual_override}
                  onCheckedChange={(value) => handleUpdatePolicy({ allow_manual_override: value })}
                  disabled={saving}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label htmlFor="manual_override_requires_reason" className="text-base font-semibold">
                    Require Reason for Manual Override
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    When enabled, manual overrides require a reason to be provided.
                  </p>
                </div>
                <Switch
                  id="manual_override_requires_reason"
                  checked={policy.manual_override_requires_reason}
                  onCheckedChange={(value) => handleUpdatePolicy({ manual_override_requires_reason: value })}
                  disabled={saving || !policy.allow_manual_override}
                />
              </div>
            </CardContent>
          </Card>

          <Alert className="border-blue-500 bg-blue-50">
            <Info className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-800">
              <strong>Important:</strong> Recommendation Health is input readiness, not release approval.
              Release Decision controls the Quality Gate. PARTIAL means release is not fully verified.
              UNKNOWN means Veriscope could not generate a release decision.
            </AlertDescription>
          </Alert>
        </TabsContent>

        <TabsContent value="governance" className="space-y-6">
          {/* Effective Policy */}
          {effectivePolicy && (
            <Card>
              <CardHeader>
                <CardTitle>Effective Policy</CardTitle>
                <CardDescription>Current policy in effect with inheritance information</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-semibold">Policy Source</Label>
                    <p className="text-sm">{effectivePolicy.source}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-semibold">Source Preset</Label>
                    <p className="text-sm">{effectivePolicy.source_preset || 'Custom'}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-semibold">Repository Override Exists</Label>
                    <p className="text-sm">{effectivePolicy.repository_override_exists ? 'Yes' : 'No'}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-semibold">Drift from Default</Label>
                    <p className={`text-sm font-semibold ${effectivePolicy.drift_from_default ? 'text-red-600' : 'text-green-600'}`}>
                      {effectivePolicy.drift_from_default ? 'Yes' : 'No'}
                    </p>
                  </div>
                </div>
                {effectivePolicy.drift_from_default && effectivePolicy.drift_fields.length > 0 && (
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Drift fields: {effectivePolicy.drift_fields.join(', ')}
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          )}

          {/* Policy Drift */}
          {policyDrift && policyDrift.drift_detected && (
            <Card>
              <CardHeader>
                <CardTitle>Policy Drift Detection</CardTitle>
                <CardDescription>Differences from organization default policy</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-semibold">Risk Level</Label>
                    <p className={`text-sm font-semibold ${
                      policyDrift.risk_level === 'HIGH' ? 'text-red-600' :
                      policyDrift.risk_level === 'MEDIUM' ? 'text-yellow-600' :
                      'text-gray-600'
                    }`}>
                      {policyDrift.risk_level}
                    </p>
                  </div>
                  <div>
                    <Label className="text-sm font-semibold">Recommended Action</Label>
                    <p className="text-sm">{policyDrift.recommended_action}</p>
                  </div>
                </div>
                {policyDrift.drift_fields.length > 0 && (
                  <div>
                    <Label className="text-sm font-semibold">Drift Fields</Label>
                    <ul className="list-disc list-inside text-sm text-muted-foreground">
                      {policyDrift.drift_fields.map((field, idx) => (
                        <li key={idx}>{field}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Preset Recommendation */}
          {presetRecommendation && (
            <Card>
              <CardHeader>
                <CardTitle>Preset Recommendation</CardTitle>
                <CardDescription>AI-recommended preset based on repository risk profile</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-semibold">Recommended Preset</Label>
                    <p className="text-sm font-semibold">{presetRecommendation.recommended_preset}</p>
                  </div>
                  <div>
                    <Label className="text-sm font-semibold">Confidence</Label>
                    <p className={`text-sm font-semibold ${
                      presetRecommendation.confidence === 'HIGH' ? 'text-green-600' :
                      presetRecommendation.confidence === 'MEDIUM' ? 'text-yellow-600' :
                      'text-gray-600'
                    }`}>
                      {presetRecommendation.confidence}
                    </p>
                  </div>
                </div>
                {presetRecommendation.reasons.length > 0 && (
                  <div>
                    <Label className="text-sm font-semibold">Reasons</Label>
                    <ul className="list-disc list-inside text-sm text-muted-foreground">
                      {presetRecommendation.reasons.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {presetRecommendation.tradeoffs.length > 0 && (
                  <div>
                    <Label className="text-sm font-semibold">Tradeoffs</Label>
                    <ul className="list-disc list-inside text-sm text-muted-foreground">
                      {presetRecommendation.tradeoffs.map((tradeoff, idx) => (
                        <li key={idx}>{tradeoff}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <Button
                  onClick={() => handleApplyPreset(presetRecommendation.recommended_preset)}
                  disabled={saving}
                >
                  Apply Recommended Preset
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Preset Selector */}
          <Card>
            <CardHeader>
              <CardTitle>Policy Presets</CardTitle>
              <CardDescription>Apply predefined policy configurations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {presets.map((preset) => (
                  <Card key={preset.name} className="cursor-pointer hover:border-primary">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">{preset.definition.name}</CardTitle>
                      <CardDescription className="text-xs">
                        Risk: {preset.definition.risk_level}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <p className="text-sm text-muted-foreground mb-2">
                        {preset.definition.recommended_use_case}
                      </p>
                      <Button
                        size="sm"
                        variant={selectedPreset === preset.name ? "default" : "outline"}
                        onClick={() => handleApplyPreset(preset.name)}
                        disabled={saving}
                        className="w-full"
                      >
                        {selectedPreset === preset.name ? 'Current' : 'Apply'}
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Import/Export */}
          <Card>
            <CardHeader>
              <CardTitle>Import / Export Policy</CardTitle>
              <CardDescription>Transfer policy configuration between repositories</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={async () => {
                    const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/export`);
                    if (response.ok) {
                      const data = await response.json();
                      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'cicd-policy.json';
                      a.click();
                    }
                  }}
                >
                  Export Policy
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = 'application/json';
                    input.onchange = async (e) => {
                      const file = (e.target as HTMLInputElement).files?.[0];
                      if (file) {
                        const text = await file.text();
                        const data = JSON.parse(text);
                        const response = await fetch(`/api/repositories/${params.repositoryId}/cicd/policy/import`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify(data),
                        });
                        if (response.ok) {
                          await loadPolicy();
                          await loadGovernanceData();
                        }
                      }
                    };
                    input.click();
                  }}
                >
                  Import Policy
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="preview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Policy Preview</CardTitle>
              <CardDescription>Preview how different scenarios will be handled by your CI/CD policy</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm font-semibold">Release Decision</Label>
                  <select
                    className="w-full p-2 border rounded"
                    value={previewScenario.releaseDecision}
                    onChange={(e) => setPreviewScenario({ ...previewScenario, releaseDecision: e.target.value })}
                  >
                    <option value="Fully Verified">Fully Verified</option>
                    <option value="Partially Verified">Partially Verified</option>
                    <option value="Not Verified">Not Verified</option>
                    <option value="Blocked">Blocked</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm font-semibold">Recommendation Health</Label>
                  <select
                    className="w-full p-2 border rounded"
                    value={previewScenario.recommendationHealth}
                    onChange={(e) => setPreviewScenario({ ...previewScenario, recommendationHealth: e.target.value })}
                  >
                    <option value="Ready">Ready</option>
                    <option value="Not Ready">Not Ready</option>
                    <option value="Unknown">Unknown</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm font-semibold">Quality Gate</Label>
                  <select
                    className="w-full p-2 border rounded"
                    value={previewScenario.qualityGate}
                    onChange={(e) => setPreviewScenario({ ...previewScenario, qualityGate: e.target.value })}
                  >
                    <option value="PASSED">PASSED</option>
                    <option value="PARTIAL">PARTIAL</option>
                    <option value="FAILED">FAILED</option>
                    <option value="BLOCKED">BLOCKED</option>
                    <option value="UNKNOWN">UNKNOWN</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm font-semibold">Has Recommendation Run</Label>
                  <select
                    className="w-full p-2 border rounded"
                    value={previewScenario.hasRecommendationRun.toString()}
                    onChange={(e) => setPreviewScenario({ ...previewScenario, hasRecommendationRun: e.target.value === 'true' })}
                  >
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                </div>
              </div>

              <Button onClick={handlePreviewPolicy} disabled={previewing}>
                {previewing ? 'Previewing...' : 'Preview Policy'}
              </Button>

              {previewResult && (
                <div className="space-y-4 mt-6 p-4 bg-gray-50 rounded-lg">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-sm font-semibold">GitHub Conclusion</Label>
                      <p className={`text-sm font-semibold ${
                        previewResult.githubConclusion === 'success' ? 'text-green-600' :
                        previewResult.githubConclusion === 'failure' ? 'text-red-600' :
                        'text-gray-600'
                      }`}>
                        {previewResult.githubConclusion.toUpperCase()}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Would Block PR</Label>
                      <p className={`text-sm font-semibold ${previewResult.wouldBlockPr ? 'text-red-600' : 'text-green-600'}`}>
                        {previewResult.wouldBlockPr ? 'Yes' : 'No'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Quality Gate</Label>
                      <p className="text-sm">{previewResult.qualityGate}</p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Reason</Label>
                      <p className="text-sm">{previewResult.reason}</p>
                    </div>
                  </div>
                  <div>
                    <Label className="text-sm font-semibold">Rules Applied</Label>
                    <ul className="list-disc list-inside text-sm text-muted-foreground">
                      {previewResult.rulesApplied.map((rule, idx) => (
                        <li key={idx}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label className="text-sm font-semibold">Quick Scenarios</Label>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewScenario({
                      releaseDecision: 'Fully Verified',
                      recommendationHealth: 'Ready',
                      qualityGate: 'PASSED',
                      hasRecommendationRun: true,
                      hasArtifact: true,
                      hasPrComment: true
                    })}
                  >
                    Fully Verified / Ready
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewScenario({
                      releaseDecision: 'Partially Verified',
                      recommendationHealth: 'Ready',
                      qualityGate: 'PARTIAL',
                      hasRecommendationRun: true,
                      hasArtifact: true,
                      hasPrComment: true
                    })}
                  >
                    Partially Verified / Ready
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewScenario({
                      releaseDecision: 'Not Verified',
                      recommendationHealth: 'Ready',
                      qualityGate: 'FAILED',
                      hasRecommendationRun: true,
                      hasArtifact: true,
                      hasPrComment: true
                    })}
                  >
                    Not Verified / Ready
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewScenario({
                      releaseDecision: 'Blocked',
                      recommendationHealth: 'Ready',
                      qualityGate: 'BLOCKED',
                      hasRecommendationRun: true,
                      hasArtifact: true,
                      hasPrComment: true
                    })}
                  >
                    Blocked / Ready
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewScenario({
                      releaseDecision: null,
                      recommendationHealth: null,
                      qualityGate: 'UNKNOWN',
                      hasRecommendationRun: false,
                      hasArtifact: false,
                      hasPrComment: false
                    })}
                  >
                    Missing Recommendation Run
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPreviewScenario({
                      releaseDecision: null,
                      recommendationHealth: null,
                      qualityGate: 'UNKNOWN',
                      hasRecommendationRun: true,
                      hasArtifact: false,
                      hasPrComment: false
                    })}
                  >
                    Unknown Quality Gate
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="branch-protection" className="space-y-6">
          {readiness && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Branch Protection Readiness</CardTitle>
                  <CardDescription>
                    {readiness.is_ready ? (
                      <span className="text-green-600 font-semibold">Repository is ready for branch protection</span>
                    ) : (
                      <span className="text-orange-600 font-semibold">Repository has readiness issues</span>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-sm font-semibold">Required Check Name</Label>
                      <p className="text-sm text-muted-foreground">{readiness.required_check_name}</p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Policy Strictness</Label>
                      <p className="text-sm text-muted-foreground">{readiness.policy_strictness}</p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">GitHub App Installed</Label>
                      <p className="text-sm text-muted-foreground">
                        {readiness.github_app_installed ? '✅ Yes' : '❌ No'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Workflow Configured</Label>
                      <p className="text-sm text-muted-foreground">
                        {readiness.workflow_configured ? '✅ Yes' : '❌ No'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Checks Write Permission</Label>
                      <p className="text-sm text-muted-foreground">
                        {readiness.checks_write_permission ? '✅ Yes' : '❌ No'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Statuses Write Permission</Label>
                      <p className="text-sm text-muted-foreground">
                        {readiness.statuses_write_permission ? '✅ Yes' : '❌ No'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">PR Comment Permission</Label>
                      <p className="text-sm text-muted-foreground">
                        {readiness.pr_comment_permission ? '✅ Yes' : '❌ No'}
                      </p>
                    </div>
                    <div>
                      <Label className="text-sm font-semibold">Latest Artifact Available</Label>
                      <p className="text-sm text-muted-foreground">
                        {readiness.latest_artifact_available ? '✅ Yes' : '❌ No'}
                      </p>
                    </div>
                  </div>

                  {readiness.readiness_issues.length > 0 && (
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        <strong>Readiness Issues:</strong>
                        <ul className="list-disc list-inside mt-2">
                          {readiness.readiness_issues.map((issue, idx) => (
                            <li key={idx}>{issue}</li>
                          ))}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  )}

                  <Alert className="border-green-500 bg-green-50">
                    <GitBranch className="h-4 w-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      <strong>Recommended Branch Protection:</strong> {readiness.recommended_branch_protection}
                    </AlertDescription>
                  </Alert>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
