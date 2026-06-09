"use client";

import { motion } from "framer-motion";
import { Github, History, Settings, ShieldCheck } from "lucide-react";

const features = [
  {
    icon: Github,
    title: "GitHub App Transparency",
    description:
      "Read-only permissions with explicit scopes. Your code never leaves your infrastructure.",
  },
  {
    icon: History,
    title: "Replayable Recommendation Lineage",
    description:
      "Every recommendation is traceable to the exact commit, model state, and evidence that produced it.",
  },
  {
    icon: Settings,
    title: "Deterministic Recommendation Engine",
    description:
      "Same inputs always produce the same outputs. No stochastic surprises in your release pipeline.",
  },
  {
    icon: ShieldCheck,
    title: "Audit-Safe Evidence Tracking",
    description:
      "Immutable snapshots of every recommendation, outcome, and override for compliance and post-mortems.",
  },
];

export function SecuritySection() {
  return (
    <section id="security" className="py-24 lg:py-32 bg-gradient-to-b from-white via-zinc-50/40 to-white relative overflow-hidden">
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-radial from-zinc-100/50 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
          className="max-w-2xl mx-auto text-center mb-16 lg:mb-20 relative"
        >
          <div className="text-xs font-semibold text-zinc-500 uppercase tracking-[0.2em] mb-4">
            Security & Trust
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-semibold tracking-tight text-zinc-900 mb-6 leading-[1.1]">
            Built for Enterprise Engineering Teams
          </h2>
          <p className="text-lg text-zinc-600 leading-relaxed">
            Security, transparency, and operational trust by design — not
            afterthought.
          </p>
        </motion.div>

        {/* Feature Grid */}
        <div className="grid sm:grid-cols-2 gap-6 lg:gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
              whileHover={{ y: -4, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] } }}
              className="group"
            >
              <div className="h-full p-6 lg:p-8 rounded-2xl bg-gradient-to-b from-white to-zinc-50/50 border border-zinc-200/70 hover:border-zinc-300/80 shadow-[0_1px_3px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_-10px_rgba(0,0,0,0.08)] transition-all duration-500">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-b from-white to-zinc-50 border border-zinc-200 flex items-center justify-center mb-5 shadow-sm group-hover:shadow-md group-hover:scale-105 transition-all duration-500">
                  <feature.icon className="w-5 h-5 text-zinc-700" />
                </div>
                <h3 className="text-lg font-semibold text-zinc-900 mb-2 tracking-tight">
                  {feature.title}
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
