"use client";

interface JumpNavSection {
  id: string;
  label: string;
}

export default function JumpNav({ sections }: { sections: JumpNavSection[] }) {
  if (sections.length === 0) return null;

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="sticky top-0 z-20 -mx-6 mb-6 border-b border-slate-200 bg-white/90 px-6 py-2 backdrop-blur">
      <div className="mx-auto flex max-w-6xl gap-4 overflow-x-auto">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => scrollTo(s.id)}
            className="shrink-0 whitespace-nowrap text-sm font-medium text-slate-500 hover:text-indigo-600"
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
