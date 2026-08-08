import { proxyBackend } from "@/lib/server/proxyBackend";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string }> }
) {
  const { recommendationRunId } = await params;
  const encodedRunId = encodeURIComponent(recommendationRunId);
  return proxyBackend({
    method: "GET",
    path: `/api/recommendations/${encodedRunId}/release-decision`,
    request,
  });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string }> }
) {
  const { recommendationRunId } = await params;
  const encodedRunId = encodeURIComponent(recommendationRunId);
  return proxyBackend({
    method: "POST",
    path: `/api/recommendations/${encodedRunId}/release-decision`,
    request,
  });
}
