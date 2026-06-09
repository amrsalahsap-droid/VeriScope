"use client";

import { Button } from "@/components/ui/button";
import { Github } from "lucide-react";
import Link from "next/link";
import { signIn } from "next-auth/react";

export default function SignupPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-zinc-50 via-white to-white flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-radial from-zinc-200/40 via-zinc-100/20 to-transparent rounded-full blur-3xl -z-10" />
      <div className="absolute top-40 right-0 w-[500px] h-[500px] bg-gradient-radial from-zinc-100/60 to-transparent rounded-full blur-3xl -z-10" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="w-8 h-8 rounded-lg bg-zinc-900 flex items-center justify-center">
              <span className="text-white font-bold text-sm">V</span>
            </div>
            <span className="font-semibold text-zinc-900 tracking-tight text-lg">
              VERISCOPE
            </span>
          </Link>
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-900 mb-2">
            Start Your Regression Intelligence Pilot
          </h2>
          <p className="text-sm text-zinc-500">
            Connect your GitHub repositories to get intelligent test recommendations
          </p>
        </div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-xl p-8">
          <div className="space-y-6">
            <div className="text-center">
              <p className="text-sm text-zinc-600 mb-4">
                Sign up with your GitHub account to get started
              </p>
            </div>

            <Button
              onClick={() => signIn("github", { callbackUrl: "/onboarding/github" })}
              className="w-full flex items-center justify-center gap-3 bg-zinc-900 text-white hover:bg-zinc-800 font-medium py-3 transition-all duration-300"
            >
              <Github className="w-5 h-5" />
              Continue with GitHub
            </Button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-zinc-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-zinc-500">
                  Enterprise-grade security
                </span>
              </div>
            </div>

            <div className="text-center space-y-2">
              <p className="text-xs text-zinc-500">
                By continuing, you agree to our{" "}
                <Link href="/terms" className="text-zinc-700 hover:text-zinc-900 underline">
                  Terms of Service
                </Link>{" "}
                and{" "}
                <Link href="/privacy" className="text-zinc-700 hover:text-zinc-900 underline">
                  Privacy Policy
                </Link>
              </p>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-zinc-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-zinc-900 hover:text-zinc-700 transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
