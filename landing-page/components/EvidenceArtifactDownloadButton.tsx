/**
 * Evidence Artifact Download Button Component
 * Downloads the evidence artifact JSON file for a pipeline run
 */

import React from 'react';

interface EvidenceArtifactDownloadButtonProps {
  pipelineRunId: string;
}

export function EvidenceArtifactDownloadButton({ pipelineRunId }: EvidenceArtifactDownloadButtonProps) {
  const handleDownload = async () => {
    try {
      const response = await fetch(`/api/pipeline-runs/${pipelineRunId}/artifact`);
      if (!response.ok) {
        const data = await response.json();
        if (data.status === 'pending') {
          alert('Artifact not ready yet. Pipeline analysis is still in progress.');
          return;
        }
        throw new Error('Failed to download artifact');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'veriscope-evidence-summary.json';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading artifact:', error);
      alert('Failed to download artifact. It may not be ready yet.');
    }
  };

  return (
    <button 
      onClick={handleDownload}
      className="text-xs text-blue-400 hover:text-blue-300"
    >
      Download Evidence Artifact
    </button>
  );
}
