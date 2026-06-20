import { proxyBackend } from "@/lib/server/proxyBackend";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string }> }
) {
  const { recommendationRunId } = await params;
  const encodedRunId = encodeURIComponent(recommendationRunId);
  return proxyBackend({
    method: "GET",
    path: `/api/recommendations/${encodedRunId}/regression-evidence`,
    request,
  });
}
