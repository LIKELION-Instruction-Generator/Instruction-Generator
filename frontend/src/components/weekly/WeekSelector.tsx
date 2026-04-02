import { Link, useParams } from "react-router-dom";
import { useWeeklyWorkspace } from "../../providers/weekly-workspace";

export function WeekSelector() {
  const { weeks } = useWeeklyWorkspace();
  const { weekId } = useParams<{ weekId: string }>();

  if (weeks.length <= 1) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {weeks.map((w) => {
        const active = w.week_id === weekId;
        return (
          <Link
            className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
              active
                ? "border-orange-200 bg-orange-500 text-white shadow-[0_10px_30px_rgba(249,115,22,0.32)]"
                : "border-slate-200 bg-white text-slate-600 hover:border-orange-200 hover:text-orange-600"
            }`}
            key={w.week_id}
            to={`/weeks/${w.week_id}/hub`}
          >
            {w.week}주차
          </Link>
        );
      })}
    </div>
  );
}
