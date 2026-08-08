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
    const { include_architecture = true, include_behaviors = true, include_journeys = true, pull_request_id = null, head_commit_sha = null } = body;

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
        pull_request_id,
        head_commit_sha,
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
      status: responseBody?.status || "SUCCESS",
      run_id: responseBody?.run_id || null,
      score: responseBody?.score ?? null,
      max_score: responseBody?.max_score ?? null,
      architecture_graph_status: responseBody?.architecture_graph_status || "PROCESSING",
      behaviors_discovered: responseBody?.behaviors_discovered || 0,
      journeys_discovered: responseBody?.journeys_discovered || 0,
      specific_behaviors_created: responseBody?.specific_behaviors_created || 0,
      business_behavior_mappings_created: responseBody?.business_behavior_mappings_created || 0,
      completed_steps: responseBody?.completed_steps || [],
      failed_steps: responseBody?.failed_steps || [],
      partial_errors: responseBody?.partial_errors || [],
      readiness_reasons: responseBody?.readiness_reasons || [],
      message: responseBody?.message || "Repository intelligence refresh initiated.",
      total_duration_ms: responseBody?.total_duration_ms ?? null,
      step_durations_ms: responseBody?.step_durations_ms ?? {},
      slowest_step: responseBody?.slowest_step ?? null,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
