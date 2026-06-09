import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ repositoryId: string }> }
) {
  const session = await auth();
  const { repositoryId } = await params;

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(
      `${BACKEND}/github/repositories/${repositoryId}/test-history/summary`,
      {
        headers: {
          Authorization: `Bearer ${session.backendToken}`,
        },
        cache: "no-store",
      }
    );

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
