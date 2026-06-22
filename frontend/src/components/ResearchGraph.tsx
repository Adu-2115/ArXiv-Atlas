"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { GraphCluster, ResearchMap, RelationType } from "@/types/research";
import { colorForCluster, RELATION_COLORS, RELATION_LABELS } from "@/lib/graphTheme";

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  title: string;
  cluster_id: string;
  summary: string;
  year: string | null;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  relation_type: RelationType;
  label: string;
}

const ALL_RELATIONS: RelationType[] = [
  "builds_on",
  "contradicts",
  "shares_method",
  "shares_dataset",
  "related",
];

export default function ResearchGraph({ map }: { map: ResearchMap }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeRelations, setActiveRelations] = useState<Set<RelationType>>(
    new Set(ALL_RELATIONS)
  );

  const relationsPresent = useMemo(
    () => new Set(map.edges.map((e) => e.relation_type)),
    [map.edges]
  );

  function toggleRelation(rel: RelationType) {
    setActiveRelations((prev) => {
      const next = new Set(prev);
      if (next.has(rel)) {
        next.delete(rel);
      } else {
        next.add(rel);
      }
      return next;
    });
  }

  // Precompute adjacency for highlight-on-click.
  const neighborMap = useMemo(() => {
    const map_: Record<string, Set<string>> = {};
    for (const e of map.edges) {
      if (!map_[e.source]) map_[e.source] = new Set();
      if (!map_[e.target]) map_[e.target] = new Set();
      map_[e.source].add(e.target);
      map_[e.target].add(e.source);
    }
    return map_;
  }, [map.edges]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;
    if (map.nodes.length === 0) return;

    const width = containerRef.current.clientWidth;
    const height = width < 640 ? 420 : width < 1024 ? 500 : 600;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const zoomLayer = svg.append("g");

    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on("zoom", (event) => {
          zoomLayer.attr("transform", event.transform);
        })
    );

    const nodes: SimNode[] = map.nodes.map((n) => ({ ...n }));
    const visibleEdges = map.edges.filter((e) => activeRelations.has(e.relation_type));
    const links: SimLink[] = visibleEdges.map((e) => ({
      source: e.source,
      target: e.target,
      relation_type: e.relation_type,
      label: e.label,
    }));

    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(110)
          .strength(0.4)
      )
      .force("charge", d3.forceManyBody().strength(-260))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(38));

    const clusterIds = [...new Set(nodes.map((n) => n.cluster_id))];
    const clusterCenters = new Map<string, { x: number; y: number }>();
    clusterIds.forEach((id, i) => {
      const angle = (i / clusterIds.length) * 2 * Math.PI;
      clusterCenters.set(id, {
        x: width / 2 + Math.cos(angle) * (width / 4),
        y: height / 2 + Math.sin(angle) * (height / 4),
      });
    });
    simulation.force(
      "clusterX",
      d3.forceX<SimNode>((d) => clusterCenters.get(d.cluster_id)?.x ?? width / 2).strength(0.12)
    );
    simulation.force(
      "clusterY",
      d3.forceY<SimNode>((d) => clusterCenters.get(d.cluster_id)?.y ?? height / 2).strength(0.12)
    );

    const tooltip = d3.select(tooltipRef.current);

    const link = zoomLayer
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => RELATION_COLORS[d.relation_type] || "#cbd5e1")
      .attr("stroke-width", 1.75)
      .attr("stroke-opacity", 0.55)
      .style("cursor", "pointer")
      .on("mouseenter", (event, d) => {
        tooltip
          .style("display", "block")
          .style("left", `${event.offsetX + 12}px`)
          .style("top", `${event.offsetY + 12}px`)
          .html(
            `<div class="font-medium">${RELATION_LABELS[d.relation_type]}</div><div class="text-slate-500">${d.label}</div>`
          );
        d3.select(event.currentTarget).attr("stroke-opacity", 1).attr("stroke-width", 3);
      })
      .on("mousemove", (event) => {
        tooltip.style("left", `${event.offsetX + 12}px`).style("top", `${event.offsetY + 12}px`);
      })
      .on("mouseleave", (event) => {
        tooltip.style("display", "none");
        d3.select(event.currentTarget).attr("stroke-opacity", 0.55).attr("stroke-width", 1.75);
      });

    const node = zoomLayer
      .append("g")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", 14)
      .attr("fill", (d) => colorForCluster(d.cluster_id, map.clusters))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2)
      .style("cursor", "pointer")
      .on("click", (_, d) => {
        setSelectedId((prev) => (prev === d.id ? null : d.id));
      })
      .call(
        d3
          .drag<SVGCircleElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    const label = zoomLayer
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => (d.title.length > 28 ? d.title.slice(0, 28) + "…" : d.title))
      .attr("font-size", 10)
      .attr("dx", 18)
      .attr("dy", 4)
      .attr("fill", "#334155")
      .style("pointer-events", "none");

    // Apply highlight/dim state based on selectedId.
    function applyHighlight() {
      if (!selectedId) {
        node.attr("opacity", 1).attr("stroke", "#fff");
        link.attr("opacity", 1);
        label.attr("opacity", 1);
        return;
      }
      const neighbors = neighborMap[selectedId] || new Set();
      node
        .attr("opacity", (d) => (d.id === selectedId || neighbors.has(d.id) ? 1 : 0.15))
        .attr("stroke", (d) => (d.id === selectedId ? "#1e293b" : "#fff"));
      link.attr("opacity", (d) => {
        const s = (d.source as SimNode).id;
        const t = (d.target as SimNode).id;
        return s === selectedId || t === selectedId ? 1 : 0.06;
      });
      label.attr("opacity", (d) => (d.id === selectedId || neighbors.has(d.id) ? 1 : 0.15));
    }
    applyHighlight();

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);

      node.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      label.attr("x", (d) => d.x ?? 0).attr("y", (d) => d.y ?? 0);
    });

    return () => {
      simulation.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, activeRelations, selectedId]);

  const selectedNode = map.nodes.find((n) => n.id === selectedId) || null;

  return (
    <div className="flex flex-col gap-4">
      {/* Relation-type filter toggle */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-500">Relations:</span>
        {ALL_RELATIONS.filter((r) => relationsPresent.has(r)).map((rel) => {
          const active = activeRelations.has(rel);
          return (
            <button
              key={rel}
              onClick={() => toggleRelation(rel)}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                active
                  ? "border-slate-300 bg-white text-slate-700"
                  : "border-slate-200 bg-slate-50 text-slate-400"
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: active ? RELATION_COLORS[rel] : "#cbd5e1" }}
              />
              {RELATION_LABELS[rel]}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-4 lg:flex-row">
        <div
          ref={containerRef}
          className="relative flex-1 rounded-xl border border-slate-200 bg-white"
        >
          <svg ref={svgRef} className="h-[420px] w-full sm:h-[500px] lg:h-[600px]" />
          <div
            ref={tooltipRef}
            className="pointer-events-none absolute z-10 hidden rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-md"
            style={{ display: "none" }}
          />
        </div>

        <div className="w-full lg:w-80 shrink-0">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-500 uppercase tracking-wide">
              Clusters
            </h3>
            <ul className="space-y-2 mb-4">
              {map.clusters.map((c: GraphCluster) => (
                <li key={c.id} className="flex items-start gap-2 text-sm">
                  <span
                    className="mt-1 h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: colorForCluster(c.id, map.clusters) }}
                  />
                  <div>
                    <div className="font-medium text-slate-800">{c.label}</div>
                    <div className="text-slate-500">{c.description}</div>
                  </div>
                </li>
              ))}
            </ul>

            {selectedNode ? (
              <div className="border-t border-slate-200 pt-3">
                <h4 className="text-sm font-semibold text-slate-800">{selectedNode.title}</h4>
                {selectedNode.year && (
                  <div className="text-xs text-slate-400 mb-1">{selectedNode.year}</div>
                )}
                <p className="text-sm text-slate-600">{selectedNode.summary}</p>
                <a
                  href={`https://arxiv.org/abs/${selectedNode.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-xs font-medium text-indigo-600 hover:underline"
                >
                  View on arXiv →
                </a>
                <button
                  onClick={() => setSelectedId(null)}
                  className="mt-2 block text-xs text-slate-400 hover:text-slate-600"
                >
                  Clear selection
                </button>
              </div>
            ) : (
              <p className="border-t border-slate-200 pt-3 text-xs text-slate-400">
                Click a node to see paper details and highlight its connections.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
