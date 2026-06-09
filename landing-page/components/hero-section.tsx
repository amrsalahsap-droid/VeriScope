"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  GitPullRequest,
  Brain,
  Database,
  FileText,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Zap,
} from "lucide-react";

export function HeroSection() {
  return (
    <section className="relative pt-32 pb-20 lg:pt-40 lg:pb-32 overflow-hidden">
      {/* Background gradients */}
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-50 via-white to-white -z-10" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1200px] h-[700px] bg-gradient-radial from-zinc-200/40 via-zinc-100/20 to-transparent rounded-full blur-3xl -z-10" />
      <div className="absolute top-40 right-0 w-[500px] h-[500px] bg-gradient-radial from-zinc-100/60 to-transparent rounded-full blur-3xl -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left column - Content */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
            className="max-w-xl"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, delay: 0.1 }}
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 border border-zinc-200/80 mb-6"
            >
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs font-medium text-zinc-600">
                Now in Pilot Program
              </span>
            </motion.div>

            <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-semibold tracking-tight text-zinc-900 leading-[1.08] mb-6">
              Stop Running Your Entire Regression Suite{" "}
              <span className="text-zinc-400">Blindly</span>
            </h1>

            <p className="text-lg text-zinc-500 leading-relaxed mb-10 max-w-lg">
              Veriscope analyzes pull requests, historical failures, coverage
              signals, and organizational fragility patterns to recommend
              exactly what should be tested — and explain why.
            </p>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="flex flex-wrap gap-3 mb-14"
            >
              <Button size="lg" className="gap-2 shadow-lg shadow-zinc-900/10 hover:shadow-xl hover:shadow-zinc-900/15 transition-shadow duration-300" asChild>
                <a href="/contact">
                  Book a Pilot
                  <ArrowRight className="w-4 h-4" />
                </a>
              </Button>
              <Button variant="outline" size="lg" className="hover:bg-zinc-50 transition-colors duration-300" asChild>
                <a href="#pr-intelligence">
                  See PR Intelligence
                </a>
              </Button>
            </motion.div>

            {/* Animated flow */}
            <div className="flex items-center gap-3 text-sm text-zinc-500">
              <div className="flex items-center gap-2">
                <GitPullRequest className="w-4 h-4" />
                <span>GitHub PR</span>
              </div>
              <ArrowRight className="w-3 h-3 text-zinc-300" />
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4" />
                <span>Recommendation</span>
              </div>
              <ArrowRight className="w-3 h-3 text-zinc-300" />
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4" />
                <span>Fragility Memory</span>
              </div>
            </div>
          </motion.div>

          {/* Right column - PR Intelligence Panel */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
            className="relative"
            id="pr-intelligence"
          >
            <div className="relative bg-white rounded-xl border border-zinc-200 shadow-2xl overflow-hidden">
              {/* Panel Header */}
              <div className="px-4 py-3 border-b border-zinc-100 bg-zinc-50/50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <span className="text-xs font-medium text-zinc-500">
                  PR Intelligence
                </span>
              </div>

              {/* Panel Content */}
              <div className="p-5 space-y-4">
                {/* Changed Files */}
                <div>
                  <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                    Changed Files
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-green-600 font-mono">+47</span>
                      <FileText className="w-4 h-4 text-zinc-400" />
                      <span className="text-zinc-700">
                        src/auth/session_manager.py
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-red-600 font-mono">-12</span>
                      <FileText className="w-4 h-4 text-zinc-400" />
                      <span className="text-zinc-700">
                        src/billing/invoice.py
                      </span>
                    </div>
                  </div>
                </div>

                {/* Recommended Tests */}
                <div>
                  <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                    Recommended Regression Tests
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3 p-2 rounded-lg bg-zinc-50 border border-zinc-100">
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-zinc-700 font-medium">
                        test_session_token_validation
                      </span>
                      <span className="ml-auto text-xs text-zinc-500">
                        2.3s
                      </span>
                    </div>
                    <div className="flex items-center gap-3 p-2 rounded-lg bg-zinc-50 border border-zinc-100">
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-zinc-700 font-medium">
                        test_auth_flow_integration
                      </span>
                      <span className="ml-auto text-xs text-zinc-500">
                        4.1s
                      </span>
                    </div>
                    <div className="flex items-center gap-3 p-2 rounded-lg bg-zinc-50 border border-zinc-100">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      <span className="text-sm text-zinc-700 font-medium">
                        test_billing_invoice_edge_cases
                      </span>
                      <span className="ml-auto text-xs text-zinc-500">
                        1.8s
                      </span>
                    </div>
                  </div>
                </div>

                {/* Runtime Reduction */}
                <div className="flex items-center gap-4 p-3 rounded-lg bg-gradient-to-r from-green-50 to-emerald-50 border border-green-100">
                  <Clock className="w-5 h-5 text-green-600" />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-zinc-700">
                      Runtime Reduction
                    </div>
                    <div className="text-xs text-zinc-500">
                      Full suite: 2h 14m → Recommended: 41m
                    </div>
                  </div>
                  <div className="text-lg font-semibold text-green-600">
                    -69%
                  </div>
                </div>

                {/* Fragility Reasoning */}
                <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200">
                  <div className="flex items-start gap-3">
                    <Brain className="w-4 h-4 text-zinc-500 mt-0.5" />
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-zinc-700">
                        Fragility Memory Match
                      </div>
                      <div className="text-xs text-zinc-500 leading-relaxed">
                        Historical co-failure: session_token ↔ billing_invoice.
                        3 prior regressions linked to auth-billing proximity.
                      </div>
                    </div>
                  </div>
                </div>

                {/* Confidence & Action */}
                <div className="flex items-center justify-between pt-2 border-t border-zinc-100">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-500" />
                    <span className="text-sm text-zinc-600">
                      Confidence:{" "}
                      <span className="font-medium text-zinc-900">
                        High (87%)
                      </span>
                    </span>
                  </div>
                  <span className="text-xs font-medium px-2 py-1 rounded bg-green-100 text-green-700">
                    RECOMMENDED: Run targeted tests
                  </span>
                </div>
              </div>
            </div>

            {/* Glow behind panel */}
            <div className="absolute -inset-4 bg-gradient-to-br from-zinc-200/40 via-zinc-100/20 to-transparent rounded-2xl blur-2xl -z-10" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[110%] h-[110%] bg-gradient-radial from-zinc-200/20 to-transparent rounded-full blur-3xl -z-10" />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
