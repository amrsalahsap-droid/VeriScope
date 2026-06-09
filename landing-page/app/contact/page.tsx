import { Button } from "@/components/ui/button";
import { Mail, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function ContactPage() {
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
            Book a Pilot
          </h2>
          <p className="text-sm text-zinc-500">
            Get started with your Regression Intelligence pilot program
          </p>
        </div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-xl p-8">
          <div className="space-y-6">
            <div className="text-center">
              <p className="text-sm text-zinc-600 mb-4">
                Contact our team to schedule your pilot program
              </p>
            </div>

            <div className="space-y-4">
              <a
                href="mailto:pilot@veriscope.ai"
                className="flex items-center justify-center gap-3 w-full p-4 rounded-xl border border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50 transition-all duration-300"
              >
                <Mail className="w-5 h-5 text-zinc-500" />
                <span className="text-sm font-medium text-zinc-700">
                  pilot@veriscope.ai
                </span>
              </a>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-zinc-200" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white text-zinc-500">
                    Or
                  </span>
                </div>
              </div>

              <div className="text-center space-y-2">
                <p className="text-xs text-zinc-500">
                  Our team will respond within 24 hours
                </p>
              </div>
            </div>

            <div className="pt-4">
              <Button asChild className="w-full">
                <Link href="/signup">
                  Start Your Pilot
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Link>
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-zinc-500">
            <Link href="/" className="font-medium text-zinc-900 hover:text-zinc-700 transition-colors">
              Back to home
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
