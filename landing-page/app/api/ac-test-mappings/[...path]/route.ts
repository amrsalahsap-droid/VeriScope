import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const session = await auth();

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await params;
  const upstreamPath = path.map((segment) => encodeURIComponent(segment)).join("/");
  const search = request.nextUrl.search || "";
  const url = `${BACKEND}/ac-test-mappings/${upstreamPath}${search}`;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.backendToken}`,
  };

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  const accept = request.headers.get("accept");
  if (accept) {
    headers["Accept"] = accept;
  }

  const requestId = request.headers.get("x-request-id");
  if (requestId) {
    headers["X-Request-Id"] = requestId;
  }

  try {
    const init: RequestInit = {
      method: request.method,
      headers,
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      const text = await request.text();
      if (text) {
        init.body = text;
      }
    }

    const upstream = await fetch(url, init);
    const bodyText = await upstream.text();

    let body: any;
    const upstreamContentType = upstream.headers.get("content-type") || "";
    if (upstreamContentType.includes("application/json")) {
      try {
        body = JSON.parse(bodyText);
      } catch {
        body = { detail: bodyText || `Backend error ${upstream.status}` };
      }
    } else {
      body = bodyText
        ? { detail: bodyText }
        : { detail: `Backend error ${upstream.status}` };
    }

    return NextResponse.json(body, {
      status: upstream.status,
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        Pragma: "no-cache",
      },
    });
  } catch (err: any) {
    const message =
      err?.cause?.code === "ECONNREFUSED"
        ? "Backend is not reachable. Is the FastAPI server running on port 8000?"
        : err?.message ?? "Failed to reach backend";

    return NextResponse.json(
      { error: message, status: 502, endpoint: url },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
