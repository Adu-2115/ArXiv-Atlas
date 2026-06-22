"use client";

import { useMemo, useState } from "react";
import { Network, AlertTriangle } from "lucide-react";
import { streamResearch } from "@/lib/api";
import { colorForCluster } from "@/lib/graphTheme";
import StageProgress from "@/components/StageProgress";
import PaperList from "@/components/PaperList";
import InsightsList from "@/components/InsightsList";
import ResearchGraph from "@/components/ResearchGraph";
import JumpNav from "@/components/JumpNav";
import SectionHeader from "@/components/SectionHeader";
import { GraphSkeleton, CardListSkeleton } from "@/components/Skeletons";
import {
  PaperInsights,
  RankedPaper,
  ResearchMap,
  StageEvent,
  StageName,
} from "@/types/research";

export default function Home() {
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currentStage, setCurrentStage] = useState<StageName | null>(null);
  const [completedStages, setCompletedStages] = useState<Set<StageName>>(new Set());

  const [candidatesFound, setCandidatesFound] = useState<number | null>(null);
  const [rankedPapers, setRankedPapers] = useState<RankedPaper[]>([]);
  const [insights, setInsights] = useState<PaperInsights[]>([]);
  const [researchMap, setResearchMap] = useState<ResearchMap | null>(null);

  // Maps arxiv_id -> cluster color, so paper/insight cards visually tie back
  // to the graph's cluster colors.
  const clusterColorByPaper = useMemo(() => {
    if (!researchMap) return {};
    const map: Record<string, string> = {};
    for (const node of researchMap.nodes) {
      map[node.id] = colorForCluster(node.cluster_id, researchMap.clusters);
    }
    return map;
  }, [researchMap]);

  const jumpSections = useMemo(() => {
    const sections: { id: string; label: string }[] = [];
    if (researchMap && researchMap.nodes.length > 0) {
      sections.push({ id: "research-landscape", label: "Landscape" });
    }
    if (rankedPapers.length > 0) sections.push({ id: "ranked-papers", label: "Papers" });
    if (insights.length > 0) sections.push({ id: "insights", label: "Insights" });
    return sections;
  }, [researchMap, rankedPapers, insights]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || loading) return;

    setLoading(true);
    setError(null);
    setCurrentStage(null);
    setCompletedStages(new Set());
    setCandidatesFound(null);
    setRankedPapers([]);
    setInsights([]);
    setResearchMap(null);

    const onStage = (event: StageEvent) => {
      if (event.status === "started") {
        setCurrentStage(event.stage);
      } else if (event.status === "done") {
        setCompletedStages((prev) => new Set(prev).add(event.stage));
        if (event.stage === "find_papers" && event.count !== undefined) {
          setCandidatesFound(event.count);
        }
        if (event.stage === "extract_insights" && event.papers) {
          setRankedPapers(event.papers);
        }
        if (event.stage === "extract_insights" && event.insights) {
          setInsights(event.insights);
        }
        if (event.stage === "map_research" && event.map) {
          setResearchMap(event.map);
        }
      }
    };

    await streamResearch(
      topic.trim(),
      onStage,
      () => setLoading(false),
      (msg) => {
        setError(msg);
        setLoading(false);
      }
    );
  }

  const isLoadingResults =
    loading &&
    (currentStage === "rank_papers" || currentStage === "extract_insights") &&
    rankedPapers.length === 0;
  const isMapping = loading && currentStage === "map_research" && !researchMap;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">ArXiv Research Agent</h1>
        <p className="mt-1 text-slate-500">
          Enter a topic. The agent searches arXiv, ranks papers by relevance,
          extracts key insights, and maps the research landscape.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="mb-8 flex gap-3">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. retrieval augmented generation for code"
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="submit"
          disabled={loading || !topic.trim()}
          className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Researching…" : "Research"}
        </button>
      </form>

      {(loading || completedStages.size > 0) && (
        <div className="mb-8">
          <StageProgress currentStage={currentStage} completedStages={completedStages} />
          {candidatesFound !== null && (
            <p className="mt-2 text-xs text-slate-400">
              Found {candidatesFound} candidate papers from arXiv.
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="mb-6 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {jumpSections.length > 1 && <JumpNav sections={jumpSections} />}

      {/* Research landscape (graph) */}
      {isMapping && (
        <section className="mb-10">
          <SectionHeader icon={Network} title="Research Landscape" iconColor="#8b5cf6" />
          <GraphSkeleton />
        </section>
      )}

      {researchMap && researchMap.nodes.length > 0 && (
        <section id="research-landscape" className="mb-10">
          <SectionHeader icon={Network} title="Research Landscape" iconColor="#8b5cf6" />
          <p className="mb-4 text-sm text-slate-600">{researchMap.overview}</p>
          <ResearchGraph map={researchMap} />

          {researchMap.open_problems.length > 0 && (
            <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <h3 className="mb-2 text-sm font-semibold text-amber-800">Open Problems</h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
                {researchMap.open_problems.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Ranked papers */}
      {isLoadingResults && (
        <section className="mb-10">
          <SectionHeader icon={Network} title="Ranked Papers" iconColor="#6366f1" />
          <CardListSkeleton count={4} />
        </section>
      )}
      {rankedPapers.length > 0 && (
        <div className="mb-10">
          <PaperList papers={rankedPapers} clusterColorByPaper={clusterColorByPaper} />
        </div>
      )}

      {/* Extracted insights */}
      {isLoadingResults && (
        <section className="mb-10">
          <SectionHeader icon={Network} title="Extracted Insights" iconColor="#f59e0b" />
          <CardListSkeleton count={4} />
        </section>
      )}
      {insights.length > 0 && (
        <div className="mb-10">
          <InsightsList insights={insights} clusterColorByPaper={clusterColorByPaper} />
        </div>
      )}
    </main>
  );
}
