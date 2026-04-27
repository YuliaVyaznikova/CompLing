import sys
import os
import time
import logging
import warnings

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HUGGINGFACE_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realization.ontology_rag import OntologyRAG

for h in logging.getLogger().handlers[:]:
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
        logging.getLogger().removeHandler(h)

TEST_QUERIES = [
    "Кого убил лорд Блэквуд?",
    "В каких фильмах появляется Бенуа Бланк?",
    "Какие фильмы снял Рон Ховард?",
    "Какие фильмы снял Гай Ричи?",
    "Кто снял фильм Шерлок Холмс 2009?",
    "Какой жанр у фильма Остров проклятых?",
    "В каком городе происходит фильм Код да Винчи?",
    "Где происходит фильм Инферно?",
    "Кто такой Шерлок Холмс?",
    "Расскажи о Бенуа Бланке",
    "Какие преступления совершает Говард?",
    "Какие детективы есть в онтологии?",
    "Какие жертвы есть в фильмах?",
    "Кто расследует убийства в фильме Достать ножи?",
    "Какие преступления происходят в фильме Зодиак?",
    "В каких фильмах есть персонаж Шерлок Холмс?",
    "В каком городе происходит фильм Ангелы и демоны?",
]


def main():
    rag = OntologyRAG(
        ontology_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ontology_all_films.json"),
        model_name="qwen2.5:3b",
    )
    rag.index()

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_rag_results.txt")
    lines = []
    lines.append("=" * 70)
    lines.append(f"RAG demo {len(TEST_QUERIES)}")
    lines.append("=" * 70)

    for i, query in enumerate(TEST_QUERIES, 1):
        lines.append("")
        lines.append("─" * 70)
        lines.append(f"Q{i}: {query}")
        lines.append("─" * 70)

        t0 = time.time()
        result = rag.answer(query, top_n=10, top_m=3)
        elapsed = time.time() - t0

        lines.append(f"Финальный ответ ({elapsed:.1f}s):")
        lines.append(result["final_answer"])

        lines.append(f"Узлы фазы 2 ({len(result['phase2_nodes'])}):")
        for node in result["phase2_nodes"][:5]:
            label = node["text"].split("\n")[0].replace("Название: ", "")
            lines.append(f"  • {label} (score={node['score']:.3f})")

        lines.append(f"Узлы фазы 3 ({len(result['phase3_nodes'])}):")
        for node in result["phase3_nodes"][:3]:
            label = node["text"].split("\n")[0].replace("Название: ", "")
            lines.append(f"  • {label} (score={node['score']:.3f})")

    lines.append("")
    lines.append("=" * 70)

    output = "\n".join(lines)
    print(output)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\nРезультаты сохранены в {out_path}")


if __name__ == "__main__":
    main()