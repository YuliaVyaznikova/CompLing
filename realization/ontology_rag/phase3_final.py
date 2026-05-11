import logging
import re
from typing import List, Set, Tuple

from openai import OpenAI

from realization.ontology_rag.phase1_index import retrieve
from realization.ontology_rag.phase2_retrieve import ask_llm

logger = logging.getLogger("OntologyRAG")


def _strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'^[-*]{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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
    text_fragments: dict = None,
) -> str:
    all_texts = n_texts + m_texts
    logger.info("Phase 3: Sending %d unique context nodes to LLM", len(all_texts))

    if text_fragments:
        context = "\n\n".join(all_texts)
        selected_norms: List[str] = []
        unique_frags = []
        for uri, frags in text_fragments.items():
            for frag in frags:
                norm = " ".join(frag.split())
                dominated = False
                for i, sel in enumerate(selected_norms):
                    if norm == sel or (norm in sel and norm != sel):
                        dominated = True
                        break
                    if sel in norm and sel != norm:
                        selected_norms[i] = norm
                        unique_frags[i] = frag
                        dominated = True
                        break
                if not dominated:
                    selected_norms.append(norm)
                    unique_frags.append(frag)
        fragments_str = ""
        for frag in unique_frags:
            fragments_str += f"\n{frag}"

        prompt = (
            f"Ответь на заданный вопрос: {query}\n\n"
            f"Используя основной текст:\n{context}\n\n"
            f"Дополняя свой ответ данными текстами:\n{fragments_str}\n\n"
            f"Отвечай прямо и полно. Не упоминай онтологию, источники, тексты, описания, разметку или откуда взяты данные — даже если в вопросе есть такие слова, перефразируй ответ без них. "
            f"Не используй форматирование markdown (звёздочки, решётки, обратные кавычки и т.д.). "
            f"Используй только факты, явно указанные в тексте. Не придумывай факты."
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            final_answer = response.choices[0].message.content
        except Exception as e:
            logger.error("LLM request failed: %s", e)
            raise
    else:
        final_answer = ask_llm(query, all_texts, client, model_name)

    final_answer = _strip_markdown(final_answer)

    logger.info("Phase 3: Final answer received (%d chars)", len(final_answer))
    return final_answer