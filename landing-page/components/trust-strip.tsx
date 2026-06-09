"use client";

import { motion } from "framer-motion";

const companies = [
  "Vercel",
  "Stripe", 
  "Linear",
  "Notion",
  "Figma",
  "Shopify"
];

export function TrustStrip() {
  return (
    <section className="py-20 border-y border-zinc-100 bg-gradient-to-b from-white via-zinc-50/50 to-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
          className="text-center text-xs font-medium text-zinc-500 uppercase tracking-[0.2em] mb-12"
        >
          Built for high-velocity engineering teams
        </motion.p>

        <div className="flex flex-wrap justify-center items-center gap-x-10 sm:gap-x-14 gap-y-8">
          {companies.map((company, index) => (
            <motion.div
              key={company}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.06, ease: [0.25, 0.1, 0.25, 1] }}
              className="text-zinc-400 hover:text-zinc-700 transition-all duration-300 hover:scale-105"
            >
              <span className="text-lg font-semibold tracking-tight">
                {company}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
