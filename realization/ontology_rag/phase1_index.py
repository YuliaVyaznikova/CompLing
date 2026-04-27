import os
import pickle
import re
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from realization.embeddings import get_embeddings, cos_compare

logger = logging.getLogger("OntologyRAG")


def index(
    node_uris: List[str],
    node_texts: List[str],
    embedding_model_name: str,
    cache_dir: str,
    force_reindex: bool = False,
) -> np.ndarray:
    cache_path = os.path.join(cache_dir, "embeddings_cache.pkl")

    if not force_reindex and os.path.exists(cache_path):
        logger.info("Loading cached embeddings from %s", cache_path)
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        cached_uris = cached["uris"]
        cached_embeddings = cached["embeddings"]

        if cached_uris == node_uris:
            logger.info("Loaded %d embeddings from cache", len(node_uris))
            return cached_embeddings
        else:
            logger.info("Cache mismatch, reindexing...")

    logger.info("Computing embeddings for %d node descriptions...", len(node_texts))
    embeddings = get_embeddings(node_texts, embedding_model_name)

    os.makedirs(cache_dir, exist_ok=True)
    logger.info("Saving embeddings cache to %s", cache_path)
    with open(cache_path, "wb") as f:
        pickle.dump({"uris": node_uris, "embeddings": embeddings}, f)

    logger.info("Indexing complete. %d nodes indexed.", len(node_uris))
    return embeddings


_RU_STOPWORDS = {
    'в', 'на', 'с', 'к', 'у', 'о', 'по', 'из', 'за', 'от', 'до', 'для',
    'при', 'без', 'об', 'со', 'под', 'над', 'между', 'через',
    'и', 'а', 'но', 'или', 'не', 'что', 'как', 'где', 'кто', 'когда',
    'это', 'тот', 'этот', 'такой', 'какой', 'который', 'весь',
    'какие', 'какая', 'какое', 'каким', 'какими', 'которая', 'которые',
    'есть', 'был', 'было', 'будет', 'быть', 'может', 'могут',
    'он', 'она', 'они', 'оно', 'мы', 'вы', 'я', 'ты',
    'свой', 'мой', 'твой', 'наш', 'ваш', 'их', 'её', 'его',
    'же', 'ли', 'бы', 'даже', 'уже', 'ещё', 'тоже', 'также',
    'чем', 'тогда', 'только', 'чтобы', 'потому', 'поэтому',
    'фильм', 'фильме', 'фильмы', 'фильмов', 'фильма', 'фильмах', 'фильмами',
    'онтологии', 'онтология',
}


def _tokenize(s: str, remove_stopwords: bool = False) -> set:
    words = set(re.findall(r'\w+', s.lower()))
    if remove_stopwords:
        words = words - _RU_STOPWORDS
    return words


_RU_ENDINGS = [
    'ами', 'ями', 'ого', 'его', 'ому', 'ему', 'ыми', 'ими',
    'ах', 'ях', 'ой', 'ей', 'ую', 'юю', 'ое', 'ее',
    'ов', 'ев', 'ый', 'ий', 'ом', 'ем',
    'ам', 'ям',
    'а', 'я', 'у', 'ю', 'е', 'о', 'ы', 'и',
]


def _ru_stem(word: str) -> str:
    w = word.lower()
    for e in _RU_ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[:-len(e)]
    return w


def _keyword_score(query: str, text: str) -> float:
    q_words = _tokenize(query, remove_stopwords=True)
    t_words = _tokenize(text)
    if not q_words:
        return 0.0
    overlap = q_words & t_words
    t_stems = {_ru_stem(w) for w in t_words}
    for qw in q_words:
        stem = _ru_stem(qw)
        if stem in t_stems and qw not in overlap:
            overlap.add(qw)
    return len(overlap) / len(q_words)


def retrieve(
    query: str,
    node_uris: List[str],
    node_texts: List[str],
    embeddings: np.ndarray,
    embedding_model_name: str,
    top_n: int = 10,
    alpha: float = 0.7,
) -> List[Tuple[str, str, float]]:
    query_embedding = get_embeddings(query, embedding_model_name)

    results = []
    for i, node_emb in enumerate(embeddings):
        sem_score = cos_compare(query_embedding[0], node_emb)
        kw_score = _keyword_score(query, node_texts[i])
        combined = alpha * sem_score + (1 - alpha) * kw_score
        results.append((node_uris[i], node_texts[i], combined))

    results.sort(key=lambda x: x[2], reverse=True)
    return results[:top_n]