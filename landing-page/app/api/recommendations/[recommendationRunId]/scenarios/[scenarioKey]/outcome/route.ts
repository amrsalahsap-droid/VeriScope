import { proxyBackend } from "@/lib/server/proxyBackend";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string; scenarioKey: string }> }
) {
  const { recommendationRunId, scenarioKey } = await params;
  const encodedRunId = encodeURIComponent(recommendationRunId);
  const encodedScenarioKey = encodeURIComponent(scenarioKey);
  return proxyBackend({
    method: "PATCH",
    path: `/api/recommendations/${encodedRunId}/scenarios/${encodedScenarioKey}/outcome`,
    request,
  });
}
