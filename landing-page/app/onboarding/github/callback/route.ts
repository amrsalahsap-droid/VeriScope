import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { auth } from "@/auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const installationId = searchParams.get("installation_id");
  const setupAction = searchParams.get("setup_action");
  const state = searchParams.get("state");

  console.log('[GitHub Callback] Received callback:', {
    installation_id: installationId,
    setup_action: setupAction,
    state_present: !!state,
    full_url: request.url
  });

  // If no installation_id, user may have navigated here directly
  if (!installationId) {
    console.error('[GitHub Callback] Missing installation_id');
    return NextResponse.redirect(new URL("/onboarding/github?error=missing_installation_id", request.url));
  }

  // Get backend token: prefer state param, fall back to session
  let backendToken: string | null = state ? decodeURIComponent(state) : null;

  if (!backendToken) {
    console.log('[GitHub Callback] State missing, falling back to session token');
    const session = await auth();
    if (!session?.backendToken) {
      console.error('[GitHub Callback] No session, redirecting to login');
      return NextResponse.redirect(new URL("/login", request.url));
    }
    backendToken = session.backendToken;
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  try {
    const response = await fetch(`${apiUrl}/github/installation/link`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${backendToken}`,
      },
      body: JSON.stringify({
        installation_id: parseInt(installationId, 10),
        setup_action: setupAction || 'install',
      }),
    });

    console.log('[GitHub Callback] Backend response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[GitHub Callback] Backend error:', response.status, errorText);
      return NextResponse.redirect(new URL(`/onboarding/github?error=backend_${response.status}`, request.url));
    }

    const result = await response.json();
    console.log('[GitHub Callback] Backend success:', result);

    // Mark GitHub as connected
    const cookieStore = await cookies();
    cookieStore.set("veriscope_github_connected", "true", {
      maxAge: 60 * 60 * 24 * 365,
      path: "/",
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
    });

    return NextResponse.redirect(new URL("/onboarding/repositories", request.url));

  } catch (error) {
    console.error('[GitHub Callback] Exception:', error);
    return NextResponse.redirect(new URL("/onboarding/github?error=callback_exception", request.url));
  }
}
