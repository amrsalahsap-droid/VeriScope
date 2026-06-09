import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  try {
    const { backendToken } = await request.json();

    if (!backendToken) {
      return NextResponse.json(
        { error: "No backend token provided" },
        { status: 400 }
      );
    }

    const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    
    const res = await fetch(`${BACKEND}/auth/me`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${backendToken}`,
        "Content-Type": "application/json",
      },
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error("Failed to delete user:", errorText);
      return NextResponse.json(
        { error: "Failed to delete account", details: errorText },
        { status: res.status }
      );
    }

    // Clear onboarding cookies
    const cookieStore = await cookies();
    cookieStore.delete("veriscope_github_connected");
    cookieStore.delete("veriscope_repos_selected");

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error in delete-account API route:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
