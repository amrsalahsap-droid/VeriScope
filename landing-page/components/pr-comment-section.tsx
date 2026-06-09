"use client";

import { motion } from "framer-motion";
import {
  GitPullRequest,
  Clock,
  GitCommit,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
} from "lucide-react";

export function PRCommentSection() {
  return (
    <section className="py-24 lg:py-32 bg-gradient-to-b from-white via-zinc-50/40 to-white relative overflow-hidden">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-radial from-zinc-100/50 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
          className="max-w-2xl mx-auto text-center mb-16 relative"
        >
          <div className="text-xs font-semibold text-zinc-500 uppercase tracking-[0.2em] mb-4">
            PR Intelligence
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-semibold tracking-tight text-zinc-900 mb-6 leading-[1.1]">
            Explainable PR Intelligence
          </h2>
          <p className="text-lg text-zinc-600 leading-relaxed">
            Every recommendation arrives as a clear, evidence-backed PR comment
            that your team can review, question, and trust.
          </p>
        </motion.div>

        {/* GitHub PR Comment Mock */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, delay: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
          className="max-w-3xl mx-auto relative"
        >
          <div className="absolute -inset-4 bg-gradient-to-br from-zinc-200/30 to-transparent rounded-3xl blur-2xl pointer-events-none" />
          <div className="relative bg-white rounded-xl border border-zinc-200 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.08),0_8px_16px_-8px_rgba(0,0,0,0.06)] overflow-hidden">
            {/* PR Header */}
            <div className="px-5 py-4 border-b border-zinc-100 flex items-center gap-3">
              <GitPullRequest className="w-5 h-5 text-green-600" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-zinc-900">
                  #847 — Update session middleware & invoice validation
                </div>
                <div className="text-xs text-zinc-500 mt-0.5">
                  opened 2 hours ago by sarah.chen
                </div>
              </div>
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-100">
                Ready to merge
              </span>
            </div>

            {/* Comment Body */}
            <div className="p-5 space-y-6">
              {/* Veriscope Bot Header */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-zinc-900 flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-xs font-bold">V</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-zinc-900">
                      veriscope
                    </span>
                    <span className="text-xs text-zinc-500">bot</span>
                    <span className="text-xs text-zinc-400">• 2h ago</span>
                  </div>

                  <div className="mt-3 space-y-5">
                    {/* Recommended Suite */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-800 mb-2.5 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600" />
                        Recommended Regression Suite
                      </h4>
                      <div className="bg-zinc-50 rounded-lg border border-zinc-100 overflow-hidden">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-zinc-200">
                              <th className="text-left px-3 py-2 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                                Test
                              </th>
                              <th className="text-right px-3 py-2 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                                Est. Duration
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr className="border-b border-zinc-100">
                              <td className="px-3 py-2 font-mono text-xs text-zinc-700">
                                test_session_token_validation
                              </td>
                              <td className="px-3 py-2 text-right text-xs text-zinc-600 font-mono">
                                2.3s
                              </td>
                            </tr>
                            <tr className="border-b border-zinc-100">
                              <td className="px-3 py-2 font-mono text-xs text-zinc-700">
                                test_auth_flow_integration
                              </td>
                              <td className="px-3 py-2 text-right text-xs text-zinc-600 font-mono">
                                4.1s
                              </td>
                            </tr>
                            <tr className="border-b border-zinc-100">
                              <td className="px-3 py-2 font-mono text-xs text-zinc-700">
                                test_billing_invoice_edge_cases
                              </td>
                              <td className="px-3 py-2 text-right text-xs text-zinc-600 font-mono">
                                1.8s
                              </td>
                            </tr>
                            <tr className="bg-amber-50/50">
                              <td className="px-3 py-2 font-mono text-xs text-zinc-700">
                                test_payment_retry_full_suite
                              </td>
                              <td className="px-3 py-2 text-right text-xs text-zinc-600 font-mono">
                                8.2s
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Runtime Reduction */}
                    <div className="flex items-center gap-4 p-4 rounded-lg bg-green-50/60 border border-green-100">
                      <Clock className="w-5 h-5 text-green-600 flex-shrink-0" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-zinc-800">
                          Runtime Reduction
                        </div>
                        <div className="text-xs text-zinc-600 mt-0.5">
                          Full suite: 2h 14m → Recommended: 41m{" "}
                          <span className="font-semibold text-green-700">
                            (-69%)
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Risk Reasoning */}
                    <div>
                      <h4 className="text-sm font-semibold text-zinc-800 mb-2.5 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-amber-600" />
                        Risk Reasoning
                      </h4>
                      <ul className="space-y-2">
                        <li className="flex items-start gap-2 text-sm text-zinc-600">
                          <ArrowRight className="w-3.5 h-3.5 text-zinc-400 mt-0.5 flex-shrink-0" />
                          <span>
                            <code className="text-xs font-mono bg-zinc-100 px-1 py-0.5 rounded text-zinc-700">
                              auth/middleware.ts
                            </code>{" "}
                            has high fragility history — 4 prior regressions
                            linked to this module.
                          </span>
                        </li>
                        <li className="flex items-start gap-2 text-sm text-zinc-600">
                          <ArrowRight className="w-3.5 h-3.5 text-zinc-400 mt-0.5 flex-shrink-0" />
                          <span>
                            Auth and billing modules have co-failed in 2
                            previous regressions within the last 90 days.
                          </span>
                        </li>
                        <li className="flex items-start gap-2 text-sm text-zinc-600">
                          <ArrowRight className="w-3.5 h-3.5 text-zinc-400 mt-0.5 flex-shrink-0" />
                          <span>
                            Coverage signal indicates the payment retry path was
                            touched but not exercised by unit tests.
                          </span>
                        </li>
                      </ul>
                    </div>

                    {/* Recommended Action */}
                    <div className="flex items-center justify-between pt-3 border-t border-zinc-100">
                      <div className="flex items-center gap-2">
                        <GitCommit className="w-4 h-4 text-zinc-500" />
                        <span className="text-sm text-zinc-600">
                          Confidence:{" "}
                          <span className="font-semibold text-zinc-900">
                            High
                          </span>
                        </span>
                      </div>
                      <span className="text-xs font-medium px-3 py-1.5 rounded-md bg-zinc-900 text-white">
                        Run recommended suite
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Decorative caption */}
          <p className="text-center text-xs text-zinc-400 mt-6">
            Veriscope posts recommendations directly on every pull request.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
