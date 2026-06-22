import { GraphCluster } from "@/types/research";

export const CLUSTER_COLORS = [
  "#6366f1", // indigo
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ef4444", // red
  "#22c55e", // green
];

export function colorForCluster(clusterId: string, clusters: GraphCluster[]): string {
  const idx = clusters.findIndex((c) => c.id === clusterId);
  if (idx === -1) return "#94a3b8"; // slate-400 fallback
  return CLUSTER_COLORS[idx % CLUSTER_COLORS.length];
}

export const RELATION_LABELS: Record<string, string> = {
  builds_on: "Builds on",
  contradicts: "Contradicts",
  shares_method: "Shares method",
  shares_dataset: "Shares dataset",
  related: "Related",
};

export const RELATION_COLORS: Record<string, string> = {
  builds_on: "#6366f1",
  contradicts: "#ef4444",
  shares_method: "#14b8a6",
  shares_dataset: "#f59e0b",
  related: "#94a3b8",
};
