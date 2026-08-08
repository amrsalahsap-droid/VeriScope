import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ repositoryId: string; runId: string }> }
) {
  const session = await auth();
  const { repositoryId, runId } = await params;

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(`${BACKEND}/intelligence/runs/${runId}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
        "Content-Type": "application/json",
      },
    });

    const responseBody = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(
        {
          error: responseBody?.error || responseBody?.detail || `Backend error ${res.status}`,
          error_code: responseBody?.error_code,
        },
        { status: res.status }
      );
    }

    return NextResponse.json(responseBody);
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
