export function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center px-6">
      <div className="w-full max-w-md rounded-[28px] border border-orange-100 bg-white p-8 text-center shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-orange-100 border-t-orange-500" />
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-orange-500">
          Loading
        </p>
        <p className="mt-3 text-sm text-slate-500">{label}</p>
      </div>
    </div>
  );
}

export function ErrorState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center px-6">
      <div className="w-full max-w-lg rounded-[28px] border border-red-100 bg-white p-8 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-red-500">
          Data Mismatch
        </p>
        <h1 className="mt-3 text-2xl font-black tracking-tight text-slate-900">{title}</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">{description}</p>
        {onRetry ? (
          <button
            className="mt-6 rounded-full bg-orange-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-orange-600"
            onClick={onRetry}
            type="button"
          >
            Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}
