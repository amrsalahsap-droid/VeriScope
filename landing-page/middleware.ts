import { NextResponse } from "next/server";
import { auth } from "@/auth";

export default auth(async (req) => {
  const isLoggedIn = !!req.auth;
  const isApp = req.nextUrl.pathname.startsWith("/app");
  const isOnboarding = req.nextUrl.pathname === "/onboarding";
  const isOnboardingGithub = req.nextUrl.pathname === "/onboarding/github";
  const isOnboardingGithubCallback = req.nextUrl.pathname === "/onboarding/github/callback";
  const isOnboardingRepositories = req.nextUrl.pathname === "/onboarding/repositories";
  const isLogin = req.nextUrl.pathname === "/login";
  const isSignup = req.nextUrl.pathname === "/signup";
  const isContact = req.nextUrl.pathname === "/contact";
  const githubConnected = req.cookies.has("veriscope_github_connected");
  const reposSelected = req.cookies.has("veriscope_repos_selected");

  // 1. Public routes: /signup, /login, /contact are always accessible
  if (isSignup || isLogin || isContact) {
    // If authenticated user visits /signup or /login, redirect based on onboarding state
    if (isLoggedIn) {
      if (reposSelected) {
        // Fully onboarded, go to app
        return NextResponse.redirect(new URL("/app", req.nextUrl.origin));
      } else if (githubConnected) {
        // GitHub connected but repos not selected
        return NextResponse.redirect(new URL("/onboarding/repositories", req.nextUrl.origin));
      } else {
        // Not connected to GitHub App
        return NextResponse.redirect(new URL("/onboarding/github", req.nextUrl.origin));
      }
    }
    // Unauthenticated: allow access
    return NextResponse.next();
  }

  // 2. Installation callback: always allow (needed for GitHub App redirect)
  if (isOnboardingGithubCallback) {
    return NextResponse.next();
  }

  // 3. Unauthenticated users: Redirect /app or /onboarding to /login
  if ((isApp || isOnboarding || isOnboardingGithub || isOnboardingRepositories) && !isLoggedIn) {
    const loginUrl = new URL("/login", req.nextUrl.origin);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 4. Protected onboarding state machine
  if (isLoggedIn) {
    // /app requires full onboarding completion
    if (isApp) {
      if (!githubConnected) {
        return NextResponse.redirect(new URL("/onboarding/github", req.nextUrl.origin));
      }
      if (!reposSelected) {
        return NextResponse.redirect(new URL("/onboarding/repositories", req.nextUrl.origin));
      }
    }

    // /onboarding/github: if already connected, skip to repo selection
    if (isOnboardingGithub && githubConnected) {
      return NextResponse.redirect(new URL("/onboarding/repositories", req.nextUrl.origin));
    }

    // /onboarding/repositories: if repos already selected, go to app
    if (isOnboardingRepositories && reposSelected) {
      return NextResponse.redirect(new URL("/app", req.nextUrl.origin));
    }

    // /onboarding/repositories: if GitHub not connected, go back to GitHub onboarding
    if (isOnboardingRepositories && !githubConnected) {
      return NextResponse.redirect(new URL("/onboarding/github", req.nextUrl.origin));
    }
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes, except for auth)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!api/auth|_next/static|_next/image|favicon.ico|$).*)",
  ],
};
