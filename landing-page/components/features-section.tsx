"use client";

import { motion } from "framer-motion";
import { FileText, Database, ShieldCheck } from "lucide-react";

const features = [
  {
    icon: FileText,
    title: "Explainable Recommendations",
    description:
      "Every recommended test includes evidence-backed reasoning.",
  },
  {
    icon: Database,
    title: "Organizational Fragility Memory",
    description:
      "Veriscope remembers recurring failure patterns across repositories.",
  },
  {
    icon: ShieldCheck,
    title: "Operational Trust",
    description:
      "Built for calm, deterministic release decisions — not AI guesswork.",
  },
];

export function FeaturesSection() {
  return (
    <section id="product" className="py-24 lg:py-32 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
          className="max-w-3xl mx-auto text-center mb-16 lg:mb-20"
        >
          <div className="text-xs font-semibold text-zinc-500 uppercase tracking-[0.2em] mb-4">
            Product
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-semibold tracking-tight text-zinc-900 leading-[1.1]">
            Regression Intelligence That Learns How Your System Breaks
          </h2>
        </motion.div>

        {/* Feature Cards */}
        <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
              whileHover={{ y: -6, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] } }}
              className="group relative"
            >
              <div className="relative h-full p-8 rounded-2xl bg-gradient-to-b from-white to-zinc-50/50 border border-zinc-200/70 shadow-[0_1px_3px_rgba(0,0,0,0.02),0_1px_2px_rgba(0,0,0,0.03)] hover:shadow-[0_10px_40px_-15px_rgba(0,0,0,0.1),0_4px_12px_-4px_rgba(0,0,0,0.05)] hover:border-zinc-300/80 transition-all duration-500">
                {/* Icon */}
                <div className="w-12 h-12 rounded-xl bg-gradient-to-b from-white to-zinc-50 border border-zinc-200 flex items-center justify-center mb-6 shadow-sm group-hover:shadow-md group-hover:scale-[1.03] transition-all duration-500">
                  <feature.icon className="w-5 h-5 text-zinc-700" />
                </div>

                {/* Content */}
                <h3 className="text-xl font-semibold text-zinc-900 mb-3 tracking-tight">
                  {feature.title}
                </h3>
                <p className="text-zinc-500 leading-relaxed">
                  {feature.description}
                </p>

                {/* Subtle corner accent glow */}
                <div className="absolute -top-px left-1/2 -translate-x-1/2 w-1/2 h-px bg-gradient-to-r from-transparent via-zinc-300 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
