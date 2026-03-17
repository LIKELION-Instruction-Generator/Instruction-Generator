import { Link, useLocation } from "react-router-dom";

const tabs = [
  { label: "학습 허브", suffix: "hub" },
  { label: "주간 퀴즈", suffix: "quiz" },
  { label: "학습 리포트", suffix: "report" },
];

export function WeekTabs({ weekId }: { weekId: string }) {
  const location = useLocation();

  return (
    <div className="flex flex-wrap items-center gap-2">
      {tabs.map((tab) => {
        const href = `/weeks/${weekId}/${tab.suffix}`;
        const active = location.pathname === href;

        return (
          <Link
            className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
              active
                ? "border-orange-200 bg-orange-500 text-white shadow-[0_10px_30px_rgba(249,115,22,0.32)]"
                : "border-slate-200 bg-white text-slate-600 hover:border-orange-200 hover:text-orange-600"
            }`}
            key={tab.suffix}
            to={href}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
