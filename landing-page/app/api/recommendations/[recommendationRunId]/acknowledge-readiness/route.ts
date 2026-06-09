import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ recommendationRunId: string }> }
) {
  const session = await auth();
  const { recommendationRunId } = await params;

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const requestBody = await request.json().catch(() => ({}));

    const res = await fetch(`${BACKEND}/api/recommendations/${recommendationRunId}/acknowledge-readiness`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });

    const body = await res.json().catch(() => ({}));

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
