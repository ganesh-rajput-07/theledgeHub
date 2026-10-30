"""python -m evaluation [--modes vector,hybrid,vector+rerank,hybrid+rerank] [--chunk-sizes 150,250]
                       [--provider mock|ollama|openai|anthropic|gemini --model M]

Builds the corpus in a separate `<db>_eval` database (your dev data is never touched), then reports
retrieval quality for each chunk size and, optionally, end-to-end answer quality with a real model.
API keys are read from the environment (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY)."""

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings
from evaluation.corpus import CORPUS

RESULTS = Path(__file__).with_name("results")
KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


def _use_eval_database() -> str:
    main = make_url(Settings().database_url)
    url = main.set(database=f"{main.database}_eval")
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    get_settings.cache_clear()

    import psycopg

    with psycopg.connect(main.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone():
            c.execute(f'CREATE DATABASE "{url.database}"')
    return url.database


def _reset_schema() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.database.session import engine

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chunk-sizes", default="250", help="comma-separated, e.g. 150,250")
    parser.add_argument(
        "--modes", default="vector,hybrid,vector+rerank,hybrid+rerank", help="retrieval modes to compare"
    )
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--provider", help="also evaluate end-to-end answers with this provider")
    parser.add_argument("--model", help="model for --provider (default: mock-1 for mock)")
    parser.add_argument("--base-url", help="Ollama URL")
    args = parser.parse_args()

    database = _use_eval_database()
    _reset_schema()

    # Imported only now: the app reads DATABASE_URL at import time.
    from app.database.session import SessionLocal
    from app.llm.factory import build_provider
    from evaluation.harness import create_workspace, evaluate_answers, evaluate_retrieval, ingest_corpus, load_dataset

    dataset = load_dataset()
    report = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "database": database, "runs": []}
    lines = [f"# RAG evaluation · {report['generated_at']}", ""]
    lines.append(
        f"{len(dataset)} questions ({sum(1 for q in dataset if q['sources'])} answerable, "
        f"{sum(1 for q in dataset if not q['sources'])} unanswerable) over {len(CORPUS)} documents / "
        f"{sum(len(pages) for pages in CORPUS.values())} pages. "
        f"Embeddings: `{get_settings().embedding_model}`."
    )

    with SessionLocal() as db, tempfile.TemporaryDirectory() as tmp:
        ingested = {}
        for size in [int(s) for s in args.chunk_sizes.split(",")]:
            for mode in args.modes.split(","):
                overlap = min(args.overlap, size // 3)
                if size not in ingested:  # ingest once per chunk size, then compare modes on the same data
                    workspace = create_workspace(db, f"chunk-{size}")
                    ingested[size] = (workspace, ingest_corpus(db, workspace.id, Path(tmp) / f"c{size}", size, overlap))
                workspace, ingest = ingested[size]
                search_mode, rerank = mode.split("+")[0], mode.endswith("+rerank")
                # Also used by the end-to-end answer pipeline below.
                get_settings().retrieval_mode, get_settings().rerank_enabled = search_mode, rerank
                retrieval = evaluate_retrieval(db, workspace.id, dataset, mode=search_mode, rerank=rerank)
                run = {
                    "mode": mode,
                    "chunk_size": size,
                    "chunk_overlap": overlap,
                    "ingestion": ingest,
                    "retrieval": retrieval.__dict__,
                }

                lines += ["", f"## {mode} · chunk size {size} (overlap {overlap}) · {ingest['chunks']} chunks", ""]
                lines += ["| Metric | " + " | ".join(f"@{k}" for k in retrieval.k_values) + " |"]
                lines += ["| --- |" + " --- |" * len(retrieval.k_values)]
                lines += ["| Recall | " + " | ".join(_pct(retrieval.recall[k]) for k in retrieval.k_values) + " |"]
                lines += ["| Hit rate | " + " | ".join(_pct(retrieval.hit_rate[k]) for k in retrieval.k_values) + " |"]
                lines += [
                    "| Precision | " + " | ".join(_pct(retrieval.precision[k]) for k in retrieval.k_values) + " |"
                ]
                lines += [
                    "",
                    f"MRR **{retrieval.mrr:.3f}** · retrieval latency p50 {retrieval.latency_ms_p50} ms, "
                    f"p95 {retrieval.latency_ms_p95} ms",
                    "",
                ]
                lines += [
                    "Top-1 accuracy by question type: "
                    + ", ".join(
                        f"{kind} {_pct(v['top1'])} (n={v['questions']})" for kind, v in retrieval.by_kind.items()
                    )
                ]
                lines += [
                    "",
                    "Not-found threshold sweep (top-1 cosine score):",
                    "",
                    "| RAG_MIN_SCORE | answerable attempted | unanswerable refused | accuracy |",
                    "| --- | --- | --- | --- |",
                ]
                for row in retrieval.thresholds:
                    lines.append(
                        f"| {row['threshold']:.2f} | {_pct(row['answerable_attempted'])} | "
                        f"{_pct(row['unanswerable_refused'])} | {_pct(row['accuracy'])} |"
                    )
                if retrieval.misses:
                    lines += ["", "Questions whose best match was not ranked first:", ""]
                    for miss in retrieval.misses:
                        got = ", ".join(f"{f} p.{p} ({s:.2f})" for f, p, s in miss["got"])
                        lines.append(f"- {miss['question']} — rank {miss['rank'] or 'not in top 8'}; got {got}")

                if args.provider:
                    key = os.environ.get(KEY_ENV.get(args.provider, ""), None)
                    llm = build_provider(args.provider, api_key=key, base_url=args.base_url)
                    model = args.model or ("mock-1" if args.provider == "mock" else None)
                    if not model:
                        parser.error("--model is required for real providers")
                    answers = evaluate_answers(db, workspace.id, dataset, llm, model)
                    run["answers"] = answers
                    header = ["Answered (answerable)", "Facts correct", "Grounded", "Citation precision"]
                    header += ["Refused (unanswerable)", "p50", "p95", "Tokens"]
                    values = [_pct(answers[k]) for k in ("answered_rate", "fact_recall", "grounded_rate")]
                    values += [_pct(answers["citation_precision"]), _pct(answers["unanswerable_refused"])]
                    values += [f"{answers['latency_ms_p50'] / 1000:.1f}s", f"{answers['latency_ms_p95'] / 1000:.1f}s"]
                    values += [str(answers["total_tokens"])]
                    lines += ["", f"### End-to-end answers · {args.provider} `{model}`", ""]
                    lines += [
                        "| " + " | ".join(header) + " |",
                        "|" + " --- |" * len(header),
                        "| " + " | ".join(values) + " |",
                    ]
                report["runs"].append(run)

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps(report, indent=2, default=str))
    (RESULTS / "latest.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nSaved {RESULTS / 'latest.md'} and latest.json")


if __name__ == "__main__":
    main()
