"use client";

import { useEffect, useState } from "react";
import { History as HistoryIcon, Loader2 } from "lucide-react";
import { fetchHistory } from "@/lib/api";
import { HistoryEntry } from "@/types/research";

function formatRelativeTime(unixSeconds: number): string {
  const diffMs = Date.now() - unixSeconds * 1000;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function HistoryPanel({
  onSelect,
}: {
  onSelect: (id: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    fetchHistory()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load history"))
      .finally(() => setLoading(false));
  }, [open]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
      >
        <HistoryIcon size={15} />
        History
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-4 text-sm text-slate-400">
              <Loader2 size={14} className="animate-spin" />
              Loading…
            </div>
          )}
          {error && <p className="px-2 py-3 text-sm text-red-600">{error}</p>}
          {!loading && !error && entries.length === 0 && (
            <p className="px-2 py-3 text-sm text-slate-400">No past searches yet.</p>
          )}
          {!loading &&
            entries.map((entry) => (
              <button
                key={entry.id}
                onClick={() => {
                  onSelect(entry.id);
                  setOpen(false);
                }}
                className="block w-full rounded-md px-2 py-2 text-left text-sm hover:bg-slate-50"
              >
                <div className="font-medium text-slate-800 truncate">{entry.topic}</div>
                <div className="text-xs text-slate-400">{formatRelativeTime(entry.created_at)}</div>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
