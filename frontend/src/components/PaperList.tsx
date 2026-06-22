"use client";

import { ScrollText } from "lucide-react";
import { RankedPaper } from "@/types/research";
import CollapsibleCard from "./CollapsibleCard";
import SectionHeader from "./SectionHeader";

export default function PaperList({
  papers,
  clusterColorByPaper,
}: {
  papers: RankedPaper[];
  clusterColorByPaper?: Record<string, string>;
}) {
  if (papers.length === 0) return null;

  return (
    <section id="ranked-papers">
      <SectionHeader icon={ScrollText} title="Ranked Papers" iconColor="#6366f1" />
      <div className="space-y-3">
        {papers.map((p) => {
          const accent = clusterColorByPaper?.[p.arxiv_id];
          return (
            <CollapsibleCard
              key={p.arxiv_id}
              accentColor={accent}
              header={
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-slate-800">{p.title}</h3>
                  {p.llm_relevance_score !== null && (
                    <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                      {p.llm_relevance_score}/100
                    </span>
                  )}
                </div>
              }
            >
              {p.llm_justification && (
                <p className="text-sm text-slate-600">{p.llm_justification}</p>
              )}
              <a
                href={`https://arxiv.org/abs/${p.arxiv_id}`}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-block text-xs font-medium text-indigo-600 hover:underline"
              >
                View on arXiv →
              </a>
            </CollapsibleCard>
          );
        })}
      </div>
    </section>
  );
}
