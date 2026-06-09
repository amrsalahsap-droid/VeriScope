"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Github,
  CheckCircle2,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { 
  setReposSelectedCookie, 
  getRepositoriesFromBackend,
  updateRepositorySelectionServer 
} from "./actions";

export const dynamic = "force-dynamic";

export default function RepositorySelectionPage() {
  const [repositories, setRepositories] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Load repositories on mount
  useEffect(() => {
    async function loadRepos() {
      try {
        const repos = await getRepositoriesFromBackend();
        setRepositories(repos);
        // Initialize selected IDs from repo state
        const initialSelected = new Set<string>(
          repos.filter((r: any) => r.selected_for_analysis).map((r: any) => r.id as string)
        );
        setSelectedIds(initialSelected);
      } catch (error) {
        console.error("Failed to load repositories:", error);
      } finally {
        setLoading(false);
      }
    }
    loadRepos();
  }, []);

  const handleCheckboxChange = (repoId: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(repoId);
    } else {
      newSelected.delete(repoId);
    }
    setSelectedIds(newSelected);
  };

  const handleContinue = async () => {
    setSubmitting(true);
    try {
      const result = await updateRepositorySelectionServer(Array.from(selectedIds));
      await setReposSelectedCookie();
      window.location.href = "/app";
    } catch (error) {
      console.error("Failed to submit selection:", error);
      alert("Failed to save repository selection. Please try again.");
      setSubmitting(false);
    }
  };

  const handleSelectAll = async () => {
    const allIds = repositories.map(r => r.id);
    setSelectedIds(new Set(allIds));
    await updateRepositorySelectionServer(allIds);
    await setReposSelectedCookie();
    window.location.href = "/app";
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-zinc-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-zinc-500 animate-spin mx-auto" />
          <p className="text-sm text-zinc-400 mt-4">Loading repositories...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-radial from-zinc-800/10 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.005)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.005)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-2xl relative z-10">
        <div className="text-center">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-semibold tracking-wider bg-zinc-900 border border-zinc-800 text-zinc-400 uppercase mb-4">
            <Github className="w-3.5 h-3.5 text-zinc-500" /> Step 3 of 3
          </span>
          <h2 className="text-3xl font-semibold tracking-tight text-white">
            Select Repositories
          </h2>
          <p className="mt-2 text-sm text-zinc-400">
            Choose which repositories to enable for Veriscope analysis
          </p>
        </div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-2xl relative z-10 space-y-6">
        {/* Repository Selection Card */}
        <div className="bg-zinc-900/40 backdrop-blur-xl p-6 border border-zinc-800 rounded-2xl">
          {repositories.length === 0 ? (
            <div className="text-center py-8 space-y-4">
              <Loader2 className="w-8 h-8 text-zinc-500 animate-spin mx-auto" />
              <div>
                <p className="text-sm text-zinc-400">No repositories synced yet.</p>
                <p className="text-xs text-zinc-500 mt-1">
                  GitHub may still be processing. You can retry or continue to the dashboard.
                </p>
              </div>
              <div className="flex gap-3 justify-center pt-2">
                <Button variant="outline" size="sm" className="text-xs border-zinc-700 text-zinc-400 hover:text-white">
                  Sync Repositories
                </Button>
                <Button size="sm" className="text-xs bg-white text-zinc-950 hover:bg-zinc-100">
                  Continue to Dashboard
                  <ArrowRight className="w-3 h-3 ml-1" />
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-semibold text-white">
                  {repositories.length} repositories available
                </p>
                <Button
                  onClick={handleSelectAll}
                  variant="ghost"
                  size="sm"
                  className="text-xs text-zinc-400 hover:text-white"
                >
                  Select All
                </Button>
              </div>

              <div className="space-y-2 max-h-96 overflow-y-auto">
                {repositories.map((repo: any) => (
                  <div
                    key={repo.id}
                    className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-zinc-900 hover:border-zinc-800 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(repo.id)}
                        onChange={(e) => handleCheckboxChange(repo.id, e.target.checked)}
                        className="w-4 h-4 rounded border-zinc-700 bg-zinc-800 text-white focus:ring-zinc-600"
                      />
                      <div className="flex items-center gap-2.5">
                        <Github className="w-4 h-4 text-zinc-500" />
                        <span className="text-sm text-zinc-300">{repo.full_name}</span>
                      </div>
                    </div>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                        selectedIds.has(repo.id)
                          ? "bg-green-500/10 text-green-400 border border-green-500/20"
                          : "bg-zinc-800 text-zinc-500 border border-zinc-700"
                      }`}
                    >
                      {selectedIds.has(repo.id) ? "Selected" : "Not Selected"}
                    </span>
                  </div>
                ))}
              </div>

              {/* Continue Button */}
              <div className="pt-6">
                <Button
                  onClick={handleContinue}
                  disabled={submitting}
                  className="w-full flex items-center justify-center gap-2 bg-white text-zinc-950 hover:bg-zinc-100 font-semibold py-2.5 transition-all duration-300"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      Continue to Dashboard
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </div>

        {/* Info Footer */}
        <div className="text-center">
          <p className="text-[11px] text-zinc-600">
            You can modify repository selection anytime from the Repositories page
          </p>
        </div>
      </div>
    </main>
  );
}
