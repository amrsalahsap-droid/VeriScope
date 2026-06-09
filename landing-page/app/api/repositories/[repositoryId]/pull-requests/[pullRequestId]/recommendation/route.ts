import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ repositoryId: string; pullRequestId: string }> }
) {
  const session = await auth();
  const { repositoryId, pullRequestId } = await params;

  console.log("=== Recommendation API Route ===");
  console.log("BACKEND URL:", BACKEND);
  console.log("repositoryId:", repositoryId);
  console.log("pullRequestId:", pullRequestId);
  console.log("session.backendToken:", session?.backendToken ? "present" : "missing");

  if (!session?.backendToken) {
    console.log("ERROR: Unauthorized - no backend token");
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await request.json();
    
    console.log("Request body:", JSON.stringify(body));
    
    const backendUrl = `${BACKEND}/api/repositories/${repositoryId}/pull-requests/${pullRequestId}/recommendation`;
    console.log("Fetching backend URL:", backendUrl);
    
    const res = await fetch(
      backendUrl,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.backendToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    );

    console.log("Backend response status:", res.status);
    console.log("Backend response ok:", res.ok);

    const responseBody = await res.json().catch(() => ({}));
    
    console.log("Backend response body:", JSON.stringify(responseBody).substring(0, 500));

    if (!res.ok) {
      return NextResponse.json(
        {
          error: responseBody?.detail || responseBody?.message || `Backend error ${res.status}`,
          error_code: responseBody?.error_code,
          detail: responseBody?.detail,
          message: responseBody?.message,
          generation_log: responseBody?.generation_log,
        },
        { status: res.status }
      );
    }

    return NextResponse.json(responseBody);
  } catch (err: any) {
    console.log("ERROR in API route:", err);
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
