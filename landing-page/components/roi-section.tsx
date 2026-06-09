"use client";

import { motion } from "framer-motion";
import {
  GitPullRequest,
  Clock,
  CheckCircle2,
  Bug,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

const metrics = [
  {
    icon: GitPullRequest,
    label: "PRs Analyzed",
    value: "1,247",
    subtext: "This quarter",
    trend: "up" as const,
  },
  {
    icon: Clock,
    label: "Avg. Runtime Reduction",
    value: "69%",
    subtext: "2h 14m → 41m",
    trend: "down" as const,
  },
  {
    icon: CheckCircle2,
    label: "Recommendation Follow Rate",
    value: "87%",
    subtext: "Engineering trust score",
    trend: "up" as const,
  },
  {
    icon: Bug,
    label: "Escaped Defect Trend",
    value: "-42%",
    subtext: "Vs. prior quarter",
    trend: "down" as const,
  },
];

const fragileModules = [
  { name: "auth/middleware.ts", score: "High", count: 4 },
  { name: "billing/invoice.py", score: "High", count: 3 },
  { name: "payments/retry.rs", score: "Medium", count: 2 },
  { name: "session/token.go", score: "Medium", count: 2 },
];

export function ROISection() {
  return (
    <section id="pilot" className="py-24 lg:py-32 bg-gradient-to-b from-white via-zinc-50/60 to-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
          className="max-w-2xl mx-auto text-center mb-16"
        >
          <div className="text-xs font-semibold text-zinc-500 uppercase tracking-[0.2em] mb-4">
            Pilot Program
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-semibold tracking-tight text-zinc-900 mb-6 leading-[1.1]">
            Pilot Results
          </h2>
          <p className="text-lg text-zinc-600 leading-relaxed">
            Conservative, evidence-backed metrics from production pilots.
          </p>
        </motion.div>

        {/* Metrics Grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6 mb-12">
          {metrics.map((metric, index) => (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.08, ease: [0.25, 0.1, 0.25, 1] }}
              whileHover={{ y: -4, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] } }}
              className="group"
            >
              <div className="h-full p-6 rounded-xl bg-white border border-zinc-200/70 shadow-[0_1px_3px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_-10px_rgba(0,0,0,0.08)] hover:border-zinc-300/80 transition-all duration-500">
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center group-hover:bg-zinc-200 transition-colors duration-300">
                    <metric.icon className="w-5 h-5 text-zinc-700" />
                  </div>
                  {metric.trend === "up" ? (
                    <TrendingUp className="w-4 h-4 text-green-600" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-green-600" />
                  )}
                </div>
                <div className="text-3xl font-semibold text-zinc-900 mb-1">
                  {metric.value}
                </div>
                <div className="text-sm font-medium text-zinc-700 mb-1">
                  {metric.label}
                </div>
                <div className="text-xs text-zinc-500">{metric.subtext}</div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Fragile Modules Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="max-w-2xl mx-auto"
        >
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <h3 className="text-sm font-semibold text-zinc-800">
              Most Fragile Modules
            </h3>
          </div>
          <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100">
                  <th className="text-left px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Module
                  </th>
                  <th className="text-center px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Risk
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    Regressions
                  </th>
                </tr>
              </thead>
              <tbody>
                {fragileModules.map((mod, i) => (
                  <tr
                    key={mod.name}
                    className={`border-b border-zinc-50 last:border-0 hover:bg-zinc-50 transition-colors duration-150`}
                  >
                    <td className="px-5 py-3 font-mono text-xs text-zinc-700">
                      {mod.name}
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span
                        className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${
                          mod.score === "High"
                            ? "bg-red-100 text-red-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {mod.score}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-xs text-zinc-600">
                      {mod.count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
