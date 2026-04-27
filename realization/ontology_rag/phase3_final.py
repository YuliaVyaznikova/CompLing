import logging
from typing import List, Set, Tuple

from openai import OpenAI

from realization.ontology_rag.phase1_index import retrieve
from realization.ontology_rag.phase2_retrieve import ask_llm

logger = logging.getLogger("OntologyRAG")


def phase3_second_retrieval(
    query: str,
    initial_answer: str,
    n_uris: Set[str],
    node_uris: List[str],
    node_texts: List[str],
    embeddings,
    embedding_model_name: str,
    client: OpenAI,
    model_name: str,
    top_m: int = 3,
) -> dict:
    logger.info("Phase 3: Retrieving additional nodes from answer embedding")
    m_results = retrieve(initial_answer, node_uris, node_texts, embeddings, embedding_model_name, top_n=len(node_uris))

    m_texts = []
    m_uris = set()
    for uri, text, score in m_results:
        if uri not in n_uris:
            m_texts.append(text)
            m_uris.add(uri)
        if len(m_texts) >= top_m:
            break

    all_texts = list(n_uris)
    logger.info("Phase 3: Found %d additional unique nodes", len(m_texts))
    return {
        "m_results": m_results,
        "m_texts": m_texts,
        "m_uris": m_uris,
    }


def phase3_final_generation(
    query: str,
    n_texts: List[str],
    m_texts: List[str],
    client: OpenAI,
    model_name: str,
) -> str:
    all_texts = n_texts + m_texts
    logger.info("Phase 3: Sending %d unique context nodes to LLM", len(all_texts))
    final_answer = ask_llm(query, all_texts, client, model_name)
    logger.info("Phase 3: Final answer received (%d chars)", len(final_answer))
    return final_answer