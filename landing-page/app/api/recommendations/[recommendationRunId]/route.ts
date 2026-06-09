import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string }> }
) {
  const session = await auth();
  const { recommendationRunId } = await params;

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    console.log("Backend token length:", session.backendToken?.length);
    console.log("Backend token prefix:", session.backendToken?.substring(0, 50));
    
    const res = await fetch(
      `${BACKEND}/api/recommendations/${recommendationRunId}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${session.backendToken}`,
        },
      }
    );

    const body = await res.json().catch(() => ({}));
    
    console.log("Backend response status:", res.status);
    console.log("Backend response body:", JSON.stringify(body).substring(0, 500));

    if (!res.ok) {
      return NextResponse.json(
        { error: body?.detail || `Backend error ${res.status}` },
        { status: res.status }
      );
    }

    return NextResponse.json(body);
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
