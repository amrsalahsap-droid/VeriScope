function CardSkeleton() {
  return (
    <div className="bg-zinc-900/[0.25] border border-zinc-800/40 rounded-xl p-5 flex flex-col gap-3.5 animate-pulse">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded bg-zinc-800/60 shrink-0" />
          <div className="h-4 w-40 rounded bg-zinc-800/60" />
        </div>
        <div className="h-5 w-16 rounded-full bg-zinc-800/60 shrink-0" />
      </div>
      <div className="h-3 w-48 rounded bg-zinc-900/60" />
      <div className="grid grid-cols-3 gap-1.5">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-zinc-950/30 rounded-lg py-2 px-1 flex flex-col items-center gap-1 border border-zinc-800/20">
            <div className="w-3.5 h-3.5 rounded bg-zinc-800/60" />
            <div className="h-4 w-5 rounded bg-zinc-800/60" />
            <div className="h-2.5 w-10 rounded bg-zinc-900/60" />
          </div>
        ))}
      </div>
      <div className="border-t border-zinc-800/30 pt-3 flex items-center justify-between">
        <div className="h-2.5 w-28 rounded bg-zinc-900/60" />
        <div className="h-5 w-16 rounded bg-zinc-800/60" />
      </div>
    </div>
  );
}

export default function RepositoriesLoading() {
  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 animate-pulse">
        <div className="space-y-2">
          <div className="h-7 w-56 rounded-lg bg-zinc-800/60" />
          <div className="h-4 w-72 rounded bg-zinc-900/60" />
        </div>
        <div className="h-9 w-32 rounded-lg bg-zinc-800/60" />
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 animate-pulse">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-zinc-900/30 border border-zinc-800/40 rounded-xl px-4 py-3.5 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-zinc-800/40 shrink-0" />
            <div className="space-y-1.5">
              <div className="h-5 w-5 rounded bg-zinc-800/60" />
              <div className="h-2.5 w-16 rounded bg-zinc-900/60" />
            </div>
          </div>
        ))}
      </div>

      {/* Cards */}
      <div className="grid sm:grid-cols-2 gap-4">
        {[0, 1, 2, 3].map((i) => <CardSkeleton key={i} />)}
      </div>
    </div>
  );
}
