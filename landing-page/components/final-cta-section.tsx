"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ArrowRight, Calendar } from "lucide-react";

export function FinalCTASection() {
  return (
    <section className="relative py-24 lg:py-32 bg-zinc-950 overflow-hidden">
      {/* Mesh background */}
      <div className="absolute inset-0 bg-gradient-to-br from-zinc-900 via-zinc-950 to-zinc-900" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-radial from-zinc-700/20 to-transparent rounded-full blur-3xl" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-gradient-radial from-zinc-800/30 to-transparent rounded-full blur-3xl" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-gradient-radial from-zinc-800/30 to-transparent rounded-full blur-3xl" />
      {/* Grid overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:48px_48px]" />

      <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h2 className="text-3xl sm:text-4xl lg:text-[3rem] font-semibold tracking-tight text-white mb-6 leading-[1.1]">
            Start Your First Regression Intelligence Pilot
          </h2>
          <p className="text-lg text-zinc-400 leading-relaxed mb-10 max-w-2xl mx-auto">
            Run Veriscope alongside your CI workflow in non-blocking advisory
            mode. See exactly how much time your team can save — with full
            evidence backing every recommendation.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              size="lg"
              className="gap-2 bg-white text-zinc-900 hover:bg-zinc-100 shadow-2xl shadow-white/10 hover:shadow-white/20 transition-all duration-300"
            >
              Book a Pilot
              <ArrowRight className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="gap-2 border-zinc-700 bg-transparent text-zinc-300 hover:bg-zinc-800/50 hover:text-white hover:border-zinc-600 transition-all duration-300"
            >
              <Calendar className="w-4 h-4" />
              Request Demo
            </Button>
          </div>

          <p className="text-xs text-zinc-600 mt-8">
            No infrastructure changes. No credit card required.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
