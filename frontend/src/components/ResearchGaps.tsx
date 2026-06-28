"use client";

import { Lightbulb, GitCompareArrows, DatabaseZap, Telescope } from "lucide-react";
import { ResearchGaps as ResearchGapsType } from "@/types/research";
import SectionHeader from "./SectionHeader";

const CATEGORIES: {
  key: keyof ResearchGapsType;
  label: string;
  icon: typeof Telescope;
  color: string;
}[] = [
  { key: "underexplored_directions", label: "Underexplored Directions", icon: Telescope, color: "#6366f1" },
  { key: "conflicting_findings", label: "Conflicting Findings", icon: GitCompareArrows, color: "#ef4444" },
  { key: "missing_benchmarks", label: "Missing Benchmarks", icon: DatabaseZap, color: "#f59e0b" },
  { key: "future_work", label: "Future Work Ideas", icon: Lightbulb, color: "#22c55e" },
];

export default function ResearchGaps({ gaps }: { gaps: ResearchGapsType }) {
  const hasAny = CATEGORIES.some((c) => gaps[c.key]?.length > 0);
  if (!hasAny) return null;

  return (
    <section id="research-gaps">
      <SectionHeader icon={Telescope} title="Research Gaps & Opportunities" iconColor="#6366f1" />
      <div className="grid gap-3 md:grid-cols-2">
        {CATEGORIES.map((cat) => {
          const items = gaps[cat.key];
          if (!items || items.length === 0) return null;
          const Icon = cat.icon;
          return (
            <div
              key={cat.key}
              className="rounded-lg border border-slate-200 bg-white p-4"
              style={{ borderLeftColor: cat.color, borderLeftWidth: 4 }}
            >
              <div className="mb-2 flex items-center gap-2">
                <Icon size={15} style={{ color: cat.color }} />
                <h3 className="text-sm font-semibold text-slate-800">{cat.label}</h3>
              </div>
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                {items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
