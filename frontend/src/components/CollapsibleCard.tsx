"use client";

import { ChevronDown } from "lucide-react";
import { useState, ReactNode } from "react";

export default function CollapsibleCard({
  accentColor,
  header,
  children,
  defaultOpen = false,
}: {
  accentColor?: string;
  header: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white overflow-hidden"
      style={accentColor ? { borderLeftColor: accentColor, borderLeftWidth: 4 } : undefined}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <div className="flex-1">{header}</div>
        <ChevronDown
          size={16}
          className={`shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}
