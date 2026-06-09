import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ repositoryId: string }> }
) {
  const session = await auth();
  const { repositoryId } = await params;

  console.log("Enable repository request:", { repositoryId, hasToken: !!session?.backendToken });

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(`${BACKEND}/github/repositories/${repositoryId}/enable`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
        "Content-Type": "application/json",
      },
    });

    console.log("Backend response status:", res.status);

    const body = await res.json().catch(() => ({}));
    console.log("Backend response body:", body);

    if (!res.ok) {
      return NextResponse.json(
        { error: body?.detail || `Backend error ${res.status}` },
        { status: res.status }
      );
    }

    return NextResponse.json(body);
  } catch (err: any) {
    console.error("Enable repository error:", err);
    return NextResponse.json(
      { error: err?.message || "Failed to reach backend" },
      { status: 502 }
    );
  }
}
