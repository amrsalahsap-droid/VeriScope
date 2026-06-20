/**
 * GitHub Actions Snippet Component
 * Displays the GitHub Actions workflow snippet for triggering Veriscope analysis
 */

import React from 'react';

export const githubActionsSnippet = [
  "name: Veriscope Quality Gate",
  "",
  "on:",
  "  pull_request:",
  "    types: [opened, synchronize, reopened]",
  "",
  "jobs:",
  "  veriscope:",
  "    runs-on: ubuntu-latest",
  "    steps:",
  "      - name: Trigger Veriscope analysis",
  "        run: |",
  "          curl -sS -X POST \"$VERISCOPE_API_URL/repositories/$VERISCOPE_REPOSITORY_ID/pipeline-runs\" \\",
  "            -H \"Authorization: Bearer $VERISCOPE_TOKEN\" \\",
  "            -H \"Content-Type: application/json\" \\",
  "            -d '{",
  "              \"provider\": \"GITHUB_ACTIONS\",",
  "              \"externalRunId\": \"${{ github.run_id }}\",",
  "              \"pullRequestNumber\": ${{ github.event.pull_request.number }},",
  "              \"commitSha\": \"${{ github.sha }}\",",
  "              \"branch\": \"${{ github.head_ref }}\",",
  "              \"triggerSource\": \"pull_request\"",
  "            }'"
].join("\n");

export function GitHubActionsSnippet() {
  return (
    <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-zinc-300 mb-2">GitHub Actions Integration</h3>
      <p className="text-xs text-zinc-500 mb-3">
        Add this snippet to your GitHub Actions workflow to trigger Veriscope analysis:
      </p>
      <pre className="bg-zinc-950 border border-zinc-800 rounded p-3 text-xs text-zinc-300 overflow-x-auto">
        {githubActionsSnippet}
      </pre>
    </div>
  );
}
