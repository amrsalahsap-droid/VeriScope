import { NextRequest } from "next/server";
import { proxyBackend } from "@/lib/server/proxyBackend";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ recommendationRunId: string }> }
) {
  const { recommendationRunId } = await params;
  const encodedRunId = encodeURIComponent(recommendationRunId);
  const mode = request.nextUrl.searchParams.get("mode") ?? "targeted";

  const backendBaseUrl = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || "";
  const cleanBaseUrl = backendBaseUrl.replace(/\/+$/, "");
  const backendUrl = new URL(`${cleanBaseUrl}/api/recommendations/${encodedRunId}/regression-scope`);
  backendUrl.searchParams.set("mode", mode);

  console.log("REGRESSION_SCOPE_PROXY_MODE", {
    receivedMode: mode,
    backendUrl: backendUrl.toString(),
  });

  return proxyBackend({
    method: "GET",
    path: `/api/recommendations/${encodedRunId}/regression-scope`,
    request,
  });
}
