from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

API_URL = os.getenv("STT_QUIZ_API_URL", "http://localhost:8000")
SHOW_PIPELINE_OPS = os.getenv("STT_QUIZ_SHOW_PIPELINE_OPS", "false").lower() == "true"


def _post(path: str, payload: dict, *, timeout: int = 120):
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _get(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def _reset_quiz_state() -> None:
    st.session_state["quiz_submitted"] = False
    st.session_state["quiz_feedback"] = None


def _score_quiz(bundle: dict[str, Any]) -> dict[str, Any]:
    quiz_items = bundle["quiz_set"]["items"]
    answers: list[int] = []
    for idx in range(len(quiz_items)):
        value = st.session_state.get(f"quiz_answer_{idx}")
        if value is None:
            raise ValueError("모든 문항에 답해야 합니다.")
        answers.append(value)

    results = []
    correct_count = 0
    for idx, item in enumerate(quiz_items):
        selected = answers[idx]
        is_correct = selected == item["answer_index"]
        if is_correct:
            correct_count += 1
        results.append(
            {
                "selected": selected,
                "is_correct": is_correct,
                "correct_index": item["answer_index"],
            }
        )

    return {
        "results": results,
        "correct_count": correct_count,
        "total_questions": len(quiz_items),
        "total_score": correct_count * 10,
        "max_score": len(quiz_items) * 10,
    }


def main() -> None:
    st.set_page_config(page_title="STT Quiz Service", layout="wide")
    st.title("STT Quiz Service")

    if SHOW_PIPELINE_OPS:
        with st.sidebar:
            st.subheader("Pipeline Ops")
            transcripts_root = st.text_input("Transcripts root", "NLP_Task2/강의 스크립트")
            curriculum_path = st.text_input("Curriculum path", "NLP_Task2/강의 커리큘럼.csv")
            output_dir = st.text_input("Prepared output dir", "artifacts/preprocessed")
            if st.button("Prepare corpus"):
                with st.spinner("Preparing corpus..."):
                    result = _post(
                        "/pipeline/prepare",
                        {
                            "transcripts_root": transcripts_root,
                            "curriculum_path": curriculum_path,
                            "output_dir": output_dir,
                        },
                        timeout=1200,
                    )
                st.success(
                    f"Prepared {result['corpora_prepared']} corpora / "
                    f"{result['targets_prepared']} targets / {result['chunks_prepared']} chunks"
                )
            if st.button("Build index"):
                with st.spinner("Building index..."):
                    result = _post("/pipeline/index", {"corpus_ids": None}, timeout=1200)
                st.success(
                    f"Indexed {result['corpora_indexed']} corpora / {result['chunks_indexed']} chunks"
                )
            if st.button("Generate latest artifacts"):
                with st.spinner("Generating artifacts..."):
                    result = _post(
                        "/pipeline/generate",
                        {
                            "corpus_ids": None,
                            "mode": "rag",
                            "num_questions": 5,
                            "choice_count": None,
                        },
                        timeout=1200,
                    )
                st.success(f"Generated {len(result)} runs")

    try:
        lectures = _get("/lectures")
    except Exception as exc:  # pragma: no cover - UI only
        st.info(f"API unavailable or no data ingested yet: {exc}")
        return

    if not lectures:
        st.warning("No ingested lectures available yet.")
        return

    corpus_map = {
        f"{corpus['date']}": corpus
        for corpus in lectures
    }
    selected_label = st.selectbox("강의 선택", list(corpus_map))
    selected = corpus_map[selected_label]
    st.caption("기본 경로는 저장된 최신 퀴즈/가이드를 조회합니다. 생성은 배치 파이프라인에서 수행합니다.")
    st.caption(
        f"주제 수: {selected.get('topic_count', 0)} | "
        f"content: {selected.get('content', '')}"
    )
    st.caption("커리큘럼 메타데이터와 실제 강의 본문이 어긋날 수 있으며, 이는 원본 강의 품질 이슈로 간주합니다.")

    if st.button("퀴즈/가이드 불러오기"):
        with st.spinner("Loading latest bundle..."):
            bundle = _get(f"/bundle/{selected['corpus_id']}")
        st.session_state["bundle"] = bundle
        _reset_quiz_state()

    bundle = st.session_state.get("bundle")
    if not bundle:
        return

    st.subheader("Quiz")
    quiz_items = bundle["quiz_set"]["items"]
    st.write(f"생성 문항 수: {len(quiz_items)}")
    st.write(f"총점 기준: {len(quiz_items) * 10}점")
    choice_breakdown = {
        "4지선다": sum(1 for item in quiz_items if item["choice_count"] == 4),
        "5지선다": sum(1 for item in quiz_items if item["choice_count"] == 5),
    }
    st.write(f"보기 구성: 4지선다 {choice_breakdown['4지선다']}문항 / 5지선다 {choice_breakdown['5지선다']}문항")

    with st.form("quiz_form"):
        for idx, item in enumerate(quiz_items, start=1):
            st.markdown(f"**Q{idx}. {item['question']}**")
            st.radio(
                f"답안 선택 {idx}",
                options=list(range(len(item["options"]))),
                format_func=lambda option_idx, opts=item["options"]: f"{option_idx + 1}. {opts[option_idx]}",
                index=None,
                key=f"quiz_answer_{idx - 1}",
            )
        submitted = st.form_submit_button("제출하기")

    if submitted:
        try:
            st.session_state["quiz_feedback"] = _score_quiz(bundle)
            st.session_state["quiz_submitted"] = True
        except ValueError as exc:
            st.warning(str(exc))

    if st.session_state.get("quiz_submitted") and st.session_state.get("quiz_feedback"):
        feedback = st.session_state["quiz_feedback"]
        st.success(
            f"채점 완료: {feedback['correct_count']} / {feedback['total_questions']} 정답, "
            f"{feedback['total_score']} / {feedback['max_score']}점"
        )
        for idx, item in enumerate(quiz_items):
            result = feedback["results"][idx]
            status = "정답" if result["is_correct"] else "오답"
            st.markdown(f"**Q{idx + 1}. {status}**")
            st.write(f"선택한 답: {result['selected'] + 1}번")
            st.write(f"정답: {result['correct_index'] + 1}번")
            st.write(f"정답 텍스트: {item['answer_text']}")
            st.caption(item["explanation"])
            st.caption(f"근거 청크: {', '.join(item['evidence_chunk_ids'])}")

    st.subheader("Study Guide")
    guide = bundle["study_guide"]
    st.write(guide["summary"])
    st.write("핵심 개념:", ", ".join(guide["key_concepts"]))
    st.write("복습 포인트:")
    for point in guide["review_points"]:
        st.write(f"- {point}")

    st.subheader("Run Details")
    run = bundle["run"]
    st.json(run)


if __name__ == "__main__":  # pragma: no cover - UI only
    main()
