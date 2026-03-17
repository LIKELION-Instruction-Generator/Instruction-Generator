import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f8f7f5] px-6">
      <div className="w-full max-w-lg rounded-[32px] border border-orange-100 bg-white p-8 text-center shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
          Missing Route
        </p>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">
          This weekly screen does not exist.
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          Use the accepted week 1 weekly routes or a week that exists in the current weekly API.
        </p>
        <Link
          className="mt-6 inline-flex rounded-full bg-orange-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-orange-600"
          to="/"
        >
          Go to weekly hub
        </Link>
      </div>
    </div>
  );
}
