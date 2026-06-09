import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// Show ALL connected active repos (not just selected_only) so users see their
// repositories regardless of whether they've explicitly selected them yet.
const REPOSITORIES_URL = `${BACKEND}/github/repositories`;

export async function GET() {
  const session = await auth();

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let res: Response | null = null;
  try {
    res = await fetch(REPOSITORIES_URL, {
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    // Parse body — guard against non-JSON responses (e.g. 502 HTML from proxy)
    let body: any;
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      body = await res.json();
    } else {
      const text = await res.text();
      body = { detail: text || `Upstream error ${res.status}` };
    }

    if (!res.ok) {
      const errorMsg =
        body?.detail ?? body?.error ?? `Backend error ${res.status}`;
      console.error(
        `[/api/repositories] Backend returned ${res.status}: ${errorMsg}`,
        { url: REPOSITORIES_URL }
      );
      return NextResponse.json(
        { error: errorMsg, status: res.status, endpoint: REPOSITORIES_URL },
        { status: res.status }
      );
    }

    // Normalise: ensure always {repositories: [...], summary: {...}}
    const repositories = body?.repositories ?? [];
    const summary = body?.summary ?? {
      connected_repositories: repositories.length,
      selected_repositories: repositories.filter(
        (r: any) => r.selected_for_analysis
      ).length,
      ready_repositories: 0,
      needs_test_history: 0,
      sync_issues: 0,
    };

    return NextResponse.json({ repositories, summary });
  } catch (err: any) {
    const message =
      err?.cause?.code === "ECONNREFUSED"
        ? "Backend is not reachable. Is the FastAPI server running on port 8000?"
        : err?.message ?? "Failed to reach backend";

    console.error(`[/api/repositories] Fetch error:`, {
      url: REPOSITORIES_URL,
      error: message,
      cause: err?.cause,
    });

    return NextResponse.json(
      {
        error: message,
        status: 502,
        endpoint: REPOSITORIES_URL,
      },
      { status: 502 }
    );
  }
}
