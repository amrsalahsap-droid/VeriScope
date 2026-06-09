import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET() {
  const session = await auth();

  if (!session?.backendToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const res = await fetch(`${BACKEND}/github/installation/status`, {
      headers: {
        Authorization: `Bearer ${session.backendToken}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    const body = await res.json();

    if (!res.ok) {
      return NextResponse.json(
        { error: body?.detail ?? `Backend error ${res.status}` },
        { status: res.status }
      );
    }

    return NextResponse.json(body);
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message ?? "Failed to reach backend" },
      { status: 502 }
    );
  }
}
