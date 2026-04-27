import logging
from typing import List, Tuple

from openai import OpenAI

from realization.ontology_rag.phase1_index import retrieve

logger = logging.getLogger("OntologyRAG")


def ask_llm(
    query: str,
    context_texts: List[str],
    client: OpenAI,
    model_name: str,
) -> str:
    context = "\n\n".join(context_texts)
    prompt = (
        f"Ниже приведены описания объектов из онтологии детективных фильмов. "
        f"Каждый объект имеет название, тип и связи с другими объектами. "
        f"Строки вида «Свойство Тип: Значение» означают, что данный объект имеет связь с объектом «Значение». "
        f"Строки вида «Имя (Тип) свойство» означают, что объект «Имя» имеет связь с данным объектом.\n\n"
        f"Ответь на вопрос прямо и полно. Перечисли все подходящие объекты, если их несколько. "
        f"Не упоминай описания, онтологию или источники. "
        f"Используй только факты, явно указанные в описаниях. Не придумывай факты.\n\n"
        f"Вопрос: {query}\n\n"
        f"Описания:\n{context}"
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("LLM request failed: %s", e)
        raise


def phase2_retrieve_and_generate(
    query: str,
    node_uris: List[str],
    node_texts: List[str],
    embeddings,
    embedding_model_name: str,
    client: OpenAI,
    model_name: str,
    top_n: int = 5,
) -> dict:
    logger.info("Phase 2: Retrieving top %d nodes for query: %s", top_n, query)
    n_results = retrieve(query, node_uris, node_texts, embeddings, embedding_model_name, top_n=top_n)

    best_score = n_results[0][2] if n_results else 0.0
    if best_score < 0.4:
        logger.info("Phase 2: Best score %.3f below threshold, question likely off-topic", best_score)
        return {
            "n_results": n_results,
            "n_texts": [],
            "n_uris": set(),
            "initial_answer": "Я не могу ответить на этот вопрос - он не относится к онтологии фильмов.",
        }

    n_texts = [text for _, text, _ in n_results]
    n_uris = set(uri for uri, _, _ in n_results)

    logger.info("Phase 2: Sending %d context nodes to LLM", len(n_texts))
    initial_answer = ask_llm(query, n_texts, client, model_name)
    logger.info("Phase 2: Initial answer received (%d chars)", len(initial_answer))

    return {
        "n_results": n_results,
        "n_texts": n_texts,
        "n_uris": n_uris,
        "initial_answer": initial_answer,
    }