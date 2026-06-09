import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ repositoryId: string }> }
) {
  const session = await auth();
  const { repositoryId } = await params;

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await request.json().catch(() => ({}));
    const { include_architecture = true, include_behaviors = true, include_journeys = true } = body;

    const res = await fetch(`${BACKEND}/intelligence/repositories/${repositoryId}/refresh`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        include_architecture,
        include_behaviors,
        include_journeys,
      }),
    });

    const responseBody = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(
        {
          error: responseBody?.message || responseBody?.detail || `Backend error ${res.status}`,
          error_code: responseBody?.error_code,
          recoverable: responseBody?.recoverable,
          next_action: responseBody?.next_action,
        },
        { status: res.status }
      );
    }

    return NextResponse.json({
      success: true,
      architecture_graph_status: responseBody?.architecture_graph_status || "PROCESSING",
      behaviors_discovered: responseBody?.behaviors_discovered || 0,
      journeys_discovered: responseBody?.journeys_discovered || 0,
      message: responseBody?.message || "Repository intelligence refresh initiated.",
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
