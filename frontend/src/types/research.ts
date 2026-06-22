export interface RankedPaper {
  arxiv_id: string;
  title: string;
  abstract: string;
  authors: string[];
  published: string | null;
  pdf_url: string | null;
  ar5iv_url: string | null;
  primary_category: string | null;
  cross_encoder_score: number;
  llm_relevance_score: number | null;
  llm_justification: string | null;
}

export interface PaperInsights {
  arxiv_id: string;
  title: string;
  problem: string;
  method: string;
  key_results: string[];
  datasets_benchmarks: string[];
  limitations: string | null;
}

export interface GraphNode {
  id: string;
  title: string;
  cluster_id: string;
  summary: string;
  relevance_score: number | null;
  year: string | null;
}

export interface GraphCluster {
  id: string;
  label: string;
  description: string;
}

export type RelationType =
  | "builds_on"
  | "contradicts"
  | "shares_method"
  | "shares_dataset"
  | "related";

export interface GraphEdge {
  source: string;
  target: string;
  relation_type: RelationType;
  label: string;
}

export interface ResearchMap {
  topic: string;
  clusters: GraphCluster[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  open_problems: string[];
  overview: string;
}

export interface PipelineResult {
  topic: string;
  candidates_found: number;
  ranked_papers: RankedPaper[];
  insights: PaperInsights[];
  research_map: ResearchMap;
}

export type StageName =
  | "find_papers"
  | "rank_papers"
  | "extract_insights"
  | "map_research";

export interface StageEvent {
  stage: StageName;
  status: "started" | "done";
  count?: number;
  papers?: RankedPaper[];
  insights?: PaperInsights[];
  map?: ResearchMap;
}
