import { useWeeklyConceptMap } from "../../hooks/useWeeklyConceptMap";

interface ConceptMapPanelProps {
  weekId: string;
}

function normalizeScore(score: number, minScore: number, maxScore: number): number {
  if (maxScore === minScore) return 0.5;
  return (score - minScore) / (maxScore - minScore);
}

function getFontSize(normalized: number): string {
  const rem = 0.75 + normalized * 1.5;
  return `${rem.toFixed(3)}rem`;
}

function getTermClassName(normalized: number): string {
  if (normalized >= 0.7) {
    return "text-orange-600 font-black";
  }
  if (normalized >= 0.4) {
    return "text-orange-400 font-bold";
  }
  if (normalized >= 0.15) {
    return "text-slate-600 font-semibold";
  }
  return "text-slate-400 font-semibold";
}

export function ConceptMapPanel({ weekId }: ConceptMapPanelProps) {
  const { data, loading, error } = useWeeklyConceptMap(weekId);

  return (
    <section className="rounded-[32px] border border-white/50 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
          개념 맵
        </p>
        <h3 className="text-kr mt-2 text-2xl font-black tracking-tight text-slate-900">
          이번 주 핵심 키워드
        </h3>
        {data && (
          <p className="mt-1 text-xs text-slate-400">
            {data.terms.length}개 키워드 · 점수 기반 크기
          </p>
        )}
      </div>

      <div className="mt-6 min-h-[180px] rounded-[24px] bg-slate-50 px-6 py-8">
        {loading && (
          <div className="flex h-full min-h-[180px] items-center justify-center">
            <p className="text-sm text-slate-400">키워드를 불러오는 중...</p>
          </div>
        )}

        {!loading && error && (
          <div className="flex h-full min-h-[180px] items-center justify-center">
            <p className="text-sm text-slate-400">키워드를 불러올 수 없습니다.</p>
          </div>
        )}

        {!loading && !error && data && (
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-3">
            {data.terms.map((term) => {
              const normalized = normalizeScore(term.score, data.min_score, data.max_score);
              return (
                <span
                  className={`cursor-default transition-opacity hover:opacity-60 ${getTermClassName(normalized)}`}
                  key={term.term}
                  style={{ fontSize: getFontSize(normalized), lineHeight: 1.3 }}
                  title={`순위 ${term.rank} · 점수 ${term.score.toFixed(2)}`}
                >
                  {term.term}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
