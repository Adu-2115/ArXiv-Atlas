"use client";

import { Search, BarChart3, FileSearch, Network } from "lucide-react";
import { StageName } from "@/types/research";

const STAGES: { key: StageName; label: string; icon: typeof Search }[] = [
  { key: "find_papers", label: "Searching arXiv", icon: Search },
  { key: "rank_papers", label: "Ranking papers", icon: BarChart3 },
  { key: "extract_insights", label: "Extracting insights", icon: FileSearch },
  { key: "map_research", label: "Mapping research", icon: Network },
];

export default function StageProgress({
  currentStage,
  completedStages,
}: {
  currentStage: StageName | null;
  completedStages: Set<StageName>;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {STAGES.map((s, i) => {
        const isDone = completedStages.has(s.key);
        const isActive = currentStage === s.key;
        const Icon = s.icon;
        return (
          <div
            key={s.key}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors ${
              isDone
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : isActive
                ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                : "border-slate-200 bg-slate-50 text-slate-400"
            }`}
          >
            <Icon size={14} className={isActive ? "animate-pulse" : ""} />
            {i + 1}. {s.label}
          </div>
        );
      })}
    </div>
  );
}
