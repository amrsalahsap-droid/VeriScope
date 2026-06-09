"use server";

import { signIn } from "@/auth";

export async function githubSignIn(callbackUrl: string) {
  await signIn("github", {
    redirectTo: callbackUrl,
  });
}
