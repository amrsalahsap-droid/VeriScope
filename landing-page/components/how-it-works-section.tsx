"use client";

import { motion } from "framer-motion";
import { Github, Database, GitPullRequest, ListChecks, ArrowRight } from "lucide-react";

const steps = [
  {
    number: "01",
    icon: Github,
    title: "Connect GitHub",
    description:
      "Install the Veriscope GitHub App with read-only permissions. No code changes required.",
  },
  {
    number: "02",
    icon: Database,
    title: "Ingest Test History",
    description:
      "We analyze your historical test runs, failures, coverage data, and CI outcomes.",
  },
  {
    number: "03",
    icon: GitPullRequest,
    title: "Analyze PR Risk",
    description:
      "Every pull request is evaluated against your organizational fragility memory.",
  },
  {
    number: "04",
    icon: ListChecks,
    title: "Recommend Targeted Regression",
    description:
      "Receive an explainable, evidence-backed test recommendation directly on the PR.",
  },
];

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-24 lg:py-32 bg-white relative overflow-hidden">
      <div className="absolute top-1/2 left-0 w-[400px] h-[400px] bg-gradient-radial from-zinc-100/40 to-transparent rounded-full blur-3xl pointer-events-none -translate-y-1/2" />
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
            Workflow
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-semibold tracking-tight text-zinc-900 mb-6 leading-[1.1]">
            How It Works
          </h2>
          <p className="text-lg text-zinc-600 leading-relaxed">
            From connection to recommendation in minutes — not months.
          </p>
        </motion.div>

        {/* Steps */}
        <div className="grid md:grid-cols-4 gap-6 lg:gap-8">
          {steps.map((step, index) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
              className="relative group"
            >
              {/* Connector line */}
              {index < steps.length - 1 && (
                <div className="hidden md:block absolute top-12 left-[60%] w-[80%]">
                  <ArrowRight className="w-4 h-4 text-zinc-300" />
                </div>
              )}

              <div className="h-full">
                {/* Step number */}
                <div className="text-xs font-semibold text-zinc-300 mb-4 tracking-wider">
                  {step.number}
                </div>

                {/* Icon */}
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-zinc-800 to-zinc-900 flex items-center justify-center mb-5 shadow-lg shadow-zinc-900/10 group-hover:shadow-xl group-hover:shadow-zinc-900/20 group-hover:scale-105 transition-all duration-500">
                  <step.icon className="w-5 h-5 text-white" />
                </div>

                {/* Content */}
                <h3 className="text-lg font-semibold text-zinc-900 mb-2 tracking-tight">
                  {step.title}
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  {step.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
