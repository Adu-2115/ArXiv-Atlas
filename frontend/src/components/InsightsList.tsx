"use client";

import { Lightbulb } from "lucide-react";
import { PaperInsights } from "@/types/research";
import CollapsibleCard from "./CollapsibleCard";
import SectionHeader from "./SectionHeader";

export default function InsightsList({
  insights,
  clusterColorByPaper,
}: {
  insights: PaperInsights[];
  clusterColorByPaper?: Record<string, string>;
}) {
  if (insights.length === 0) return null;

  return (
    <section id="insights">
      <SectionHeader icon={Lightbulb} title="Extracted Insights" iconColor="#f59e0b" />
      <div className="grid gap-3 md:grid-cols-2">
        {insights.map((ins) => {
          const accent = clusterColorByPaper?.[ins.arxiv_id];
          const failed = ins.problem === "Extraction failed";
          return (
            <CollapsibleCard
              key={ins.arxiv_id}
              accentColor={accent}
              header={<h3 className="text-sm font-semibold text-slate-800">{ins.title}</h3>}
            >
              {failed ? (
                <p className="text-sm text-amber-600">
                  Extraction failed for this paper — likely a transient rate limit. Try again later.
                </p>
              ) : (
                <>
                  <p className="mb-1 text-sm text-slate-600">
                    <span className="font-medium text-slate-700">Problem: </span>
                    {ins.problem}
                  </p>
                  <p className="mb-1 text-sm text-slate-600">
                    <span className="font-medium text-slate-700">Method: </span>
                    {ins.method}
                  </p>
                  {ins.key_results.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-sm text-slate-600">
                      {ins.key_results.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  )}
                  {ins.datasets_benchmarks.length > 0 && (
                    <p className="mt-2 text-xs text-slate-500">
                      <span className="font-medium">Datasets: </span>
                      {ins.datasets_benchmarks.join(", ")}
                    </p>
                  )}
                  {ins.limitations && (
                    <p className="mt-2 text-xs text-slate-500">
                      <span className="font-medium">Limitations: </span>
                      {ins.limitations}
                    </p>
                  )}
                </>
              )}
            </CollapsibleCard>
          );
        })}
      </div>
    </section>
  );
}
