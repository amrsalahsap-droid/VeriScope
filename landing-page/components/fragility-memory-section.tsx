"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  GitCommit,
  ArrowRightLeft,
  RotateCcw,
  Bug,
  Activity,
} from "lucide-react";

const nodes = [
  { id: "auth", label: "auth", x: 30, y: 25, status: "critical" as const },
  { id: "billing", label: "billing", x: 70, y: 25, status: "warning" as const },
  { id: "session", label: "session", x: 20, y: 55, status: "critical" as const },
  { id: "payments", label: "payments", x: 80, y: 55, status: "stable" as const },
  { id: "invoice", label: "invoice", x: 50, y: 70, status: "warning" as const },
  { id: "middleware", label: "middleware", x: 50, y: 15, status: "critical" as const },
];

const edges = [
  { from: "auth", to: "billing", type: "co-failure" as const, label: "4 co-failures" },
  { from: "session", to: "auth", type: "rollback" as const, label: "3 rollbacks" },
  { from: "middleware", to: "auth", type: "defect" as const, label: "2 defects" },
  { from: "billing", to: "invoice", type: "co-failure" as const, label: "2 co-failures" },
  { from: "payments", to: "billing", type: "unstable" as const, label: "unstable" },
];

const insights = [
  {
    icon: GitCommit,
    text: "session_token changes preceded 3 regressions",
    color: "amber",
  },
  {
    icon: ArrowRightLeft,
    text: "auth ↔ billing co-failed in 4 of last 6 releases",
    color: "red",
  },
  {
    icon: RotateCcw,
    text: "invoice module linked to 2 production rollbacks",
    color: "amber",
  },
  {
    icon: Bug,
    text: "middleware auth bypass — escaped defect lineage",
    color: "red",
  },
];

function getStatusColor(status: string) {
  switch (status) {
    case "critical":
      return "bg-red-50 border-red-200 text-red-700";
    case "warning":
      return "bg-amber-50 border-amber-200 text-amber-700";
    default:
      return "bg-green-50 border-green-200 text-green-700";
  }
}

function getEdgeColor(type: string) {
  switch (type) {
    case "co-failure":
      return "stroke-red-300";
    case "rollback":
      return "stroke-amber-300";
    case "defect":
      return "stroke-red-400";
    default:
      return "stroke-zinc-300";
  }
}

export function FragilityMemorySection() {
  return (
    <section className="py-24 lg:py-32 bg-white overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="max-w-2xl mx-auto text-center mb-16 lg:mb-20"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 border border-zinc-200 mb-6">
            <Activity className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-xs font-medium text-zinc-600">
              Organizational Memory
            </span>
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-zinc-900 mb-6">
            Your Organization&rsquo;s Reliability Memory
          </h2>
          <p className="text-lg text-zinc-600 leading-relaxed">
            Veriscope surfaces recurring failure patterns and co-failure
            relationships across your repositories — so regressions don&rsquo;t
            surprise you twice.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-5 gap-8 lg:gap-12 items-start">
          {/* Graph Visualization */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="lg:col-span-3 relative"
          >
            <div className="relative bg-zinc-50 rounded-2xl border border-zinc-200 p-8 lg:p-10 aspect-[4/3]">
              {/* SVG Graph */}
              <svg
                className="absolute inset-0 w-full h-full"
                viewBox="0 0 100 100"
                preserveAspectRatio="xMidYMid meet"
              >
                {/* Edges */}
                {edges.map((edge, i) => {
                  const from = nodes.find((n) => n.id === edge.from)!;
                  const to = nodes.find((n) => n.id === edge.to)!;
                  return (
                    <g key={i}>
                      <motion.line
                        x1={from.x}
                        y1={from.y}
                        x2={to.x}
                        y2={to.y}
                        className={`${getEdgeColor(edge.type)}`}
                        strokeWidth="0.4"
                        strokeDasharray={edge.type === "unstable" ? "2,2" : "none"}
                        initial={{ pathLength: 0 }}
                        whileInView={{ pathLength: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 1, delay: i * 0.15 }}
                      />
                      {/* Edge label background */}
                      <rect
                        x={(from.x + to.x) / 2 - 6}
                        y={(from.y + to.y) / 2 - 2.5}
                        width="12"
                        height="5"
                        rx="1"
                        className="fill-white"
                        opacity="0.9"
                      />
                      {/* Edge label */}
                      <text
                        x={(from.x + to.x) / 2}
                        y={(from.y + to.y) / 2 + 1.5}
                        className="fill-zinc-500 text-[2.5px] font-medium"
                        textAnchor="middle"
                      >
                        {edge.label}
                      </text>
                    </g>
                  );
                })}

                {/* Nodes */}
                {nodes.map((node, i) => (
                  <motion.g
                    key={node.id}
                    initial={{ opacity: 0, scale: 0 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: 0.5 + i * 0.08 }}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r="5"
                      className={
                        node.status === "critical"
                          ? "fill-red-100 stroke-red-300"
                          : node.status === "warning"
                          ? "fill-amber-100 stroke-amber-300"
                          : "fill-green-100 stroke-green-300"
                      }
                      strokeWidth="0.5"
                    />
                    <text
                      x={node.x}
                      y={node.y + 1.2}
                      className="fill-zinc-700 text-[3px] font-semibold"
                      textAnchor="middle"
                    >
                      {node.label}
                    </text>
                  </motion.g>
                ))}
              </svg>

              {/* Legend */}
              <div className="absolute bottom-4 left-4 flex items-center gap-4 text-xs text-zinc-500">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-200 border border-red-300" />
                  <span>Critical</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-200 border border-amber-300" />
                  <span>Warning</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-200 border border-green-300" />
                  <span>Stable</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Floating Insight Cards */}
          <div className="lg:col-span-2 space-y-4">
            {insights.map((insight, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: index * 0.1 }}
                whileHover={{ x: -4, transition: { duration: 0.2 } }}
                className="group"
              >
                <div
                  className={`flex items-start gap-4 p-5 rounded-xl border ${
                    insight.color === "red"
                      ? "bg-red-50/50 border-red-100 hover:border-red-200"
                      : "bg-amber-50/50 border-amber-100 hover:border-amber-200"
                  } transition-colors duration-300`}
                >
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      insight.color === "red"
                        ? "bg-red-100 text-red-600"
                        : "bg-amber-100 text-amber-600"
                    }`}
                  >
                    <insight.icon className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm text-zinc-700 leading-relaxed">
                      {insight.text}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}

            {/* Summary stat */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: 0.4 }}
              className="mt-6 p-5 rounded-xl bg-zinc-900 text-white"
            >
              <div className="flex items-center gap-3 mb-3">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-semibold">
                  Fragility Summary
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-2xl font-semibold">4</div>
                  <div className="text-xs text-zinc-400">
                    co-failure patterns
                  </div>
                </div>
                <div>
                  <div className="text-2xl font-semibold">3</div>
                  <div className="text-xs text-zinc-400">
                    rollback-linked modules
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
