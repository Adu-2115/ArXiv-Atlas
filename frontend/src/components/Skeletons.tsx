export function GraphSkeleton() {
  return (
    <div className="flex flex-col gap-4 lg:flex-row animate-pulse">
      <div className="flex-1 rounded-xl border border-slate-200 bg-white h-[600px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="flex gap-3">
            <div className="h-10 w-10 rounded-full bg-slate-200" />
            <div className="h-10 w-10 rounded-full bg-slate-200 mt-6" />
            <div className="h-10 w-10 rounded-full bg-slate-200" />
          </div>
          <div className="h-10 w-10 rounded-full bg-slate-200" />
          <p className="text-xs text-slate-400 mt-2">Building the research map…</p>
        </div>
      </div>
      <div className="w-full lg:w-80 shrink-0">
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <div className="h-3 w-20 rounded bg-slate-200" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="h-3 w-3 rounded-full bg-slate-200 mt-1" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 w-3/4 rounded bg-slate-200" />
                <div className="h-3 w-full rounded bg-slate-100" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CardListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
          <div className="h-4 w-3/4 rounded bg-slate-200" />
          <div className="h-3 w-full rounded bg-slate-100" />
          <div className="h-3 w-5/6 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
