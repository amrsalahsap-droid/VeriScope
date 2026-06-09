import { Metadata } from "next";
import { Button } from "@/components/ui/button";
import { Github } from "lucide-react";
import Link from "next/link";
import { githubSignIn } from "./actions";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sign In — Veriscope",
  description: "Access your Regression Intelligence workspace",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>;
}) {
  const resolvedParams = await searchParams;

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
            Welcome back
          </h2>
          <p className="text-sm text-zinc-500">
            Access your Regression Intelligence workspace
          </p>
        </div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-xl p-8">
          <div className="space-y-6">
            <form action={githubSignIn.bind(null, resolvedParams?.callbackUrl || "/app")}>
              <Button
                type="submit"
                className="w-full flex items-center justify-center gap-3 bg-zinc-900 text-white hover:bg-zinc-800 font-medium py-3 transition-all duration-300"
              >
                <Github className="w-5 h-5" />
                Continue with GitHub
              </Button>
            </form>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-zinc-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-zinc-500">
                  Secure authentication
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-zinc-500">
            Don't have an account?{" "}
            <Link href="/signup" className="font-medium text-zinc-900 hover:text-zinc-700 transition-colors">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
