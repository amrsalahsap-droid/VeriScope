import { proxyBackend } from "@/lib/server/proxyBackend";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string; testIdentifier: string }> }
) {
  const { recommendationRunId, testIdentifier } = await params;
  const encodedRunId = encodeURIComponent(recommendationRunId);
  const encodedTestIdentifier = encodeURIComponent(testIdentifier);
  return proxyBackend({
    method: "PATCH",
    path: `/api/recommendations/${encodedRunId}/tests/${encodedTestIdentifier}/outcome`,
    request,
  });
}
