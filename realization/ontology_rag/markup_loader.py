import json
import os
import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("OntologyRAG")


def load_all_markups(markup_dir: str) -> List[dict]:
    markups = []
    if not os.path.isdir(markup_dir):
        logger.warning("Markup directory not found: %s", markup_dir)
        return markups

    for fname in sorted(os.listdir(markup_dir)):
        if fname.endswith(".json"):
            fpath = os.path.join(markup_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                markups.append(data)
                logger.info("Loaded markup: %s (%d entities)", fname, len(data.get("entites", [])))
            except Exception as e:
                logger.error("Failed to load markup %s: %s", fname, e)

    return markups


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+(?=[А-ЯЁA-Z])', text)
    return [p.strip() for p in parts if p.strip()]


def _deduplicate_overlapping(fragments: List[str]) -> List[str]:
    normalized = [(" ".join(f.split()), f) for f in fragments]
    normalized.sort(key=lambda x: len(x[0]), reverse=True)
    result = []
    for norm, orig in normalized:
        dominated = False
        for longer_norm, _ in result:
            if norm in longer_norm and norm != longer_norm:
                dominated = True
                break
        if not dominated:
            result.append((norm, orig))
    return [orig for _, orig in result]


def build_entity_fragment_index(
    markups: List[dict],
    K: int = 2,
) -> Dict[str, List[str]]:
    uri_to_fragments: Dict[str, List[str]] = {}

    for markup in markups:
        original_text = markup.get("originalText", [])
        if not original_text:
            continue

        full_text = "\n".join(original_text)
        sentences = _split_sentences(full_text)

        text_with_ids = markup.get("textWithIds", {})
        entities = markup.get("entites", [])

        for entity in entities:
            uri = entity.get("node_uri", "")
            pos_start = entity.get("pos_start", -1)
            pos_end = entity.get("pos_end", -1)

            if not uri or pos_start < 0:
                continue

            entity_words = []
            for p in range(pos_start, pos_end + 1):
                w = text_with_ids.get(str(p), "")
                if w:
                    entity_words.append(w)
            entity_text = " ".join(entity_words)

            if not entity_text:
                continue

            entity_lower = entity_text.lower().strip(".,:;!?()«»\"'-")
            sent_idx = -1
            for i, sent in enumerate(sentences):
                if entity_lower in sent.lower():
                    sent_idx = i
                    break

            if sent_idx < 0:
                for i, sent in enumerate(sentences):
                    for ew in entity_words:
                        ew_clean = ew.lower().strip(".,:;!?()«»\"'-")
                        if len(ew_clean) >= 3 and ew_clean in sent.lower():
                            sent_idx = i
                            break
                    if sent_idx >= 0:
                        break

            if sent_idx < 0:
                continue

            start_idx = max(0, sent_idx - K)
            end_idx = min(len(sentences), sent_idx + K + 1)
            fragment = " ".join(sentences[start_idx:end_idx])

            if uri not in uri_to_fragments:
                uri_to_fragments[uri] = []
            if fragment not in uri_to_fragments[uri]:
                uri_to_fragments[uri].append(fragment)

    for uri in uri_to_fragments:
        uri_to_fragments[uri] = _deduplicate_overlapping(uri_to_fragments[uri])

    total_uris = len(uri_to_fragments)
    total_fragments = sum(len(v) for v in uri_to_fragments.values())
    logger.info("Built fragment index: %d URIs, %d total fragments", total_uris, total_fragments)

    return uri_to_fragments


def retrieve_text_fragments(
    entity_uris: List[str],
    uri_to_fragments: Dict[str, List[str]],
    query: str,
    embedding_model_name: str,
    top_l: int = 3,
) -> Dict[str, List[str]]:
    from realization.embeddings import get_embeddings, cos_compare

    if not entity_uris or not uri_to_fragments:
        return {}

    all_fragments = []
    for uri in entity_uris:
        fragments = uri_to_fragments.get(uri, [])
        for frag in fragments:
            all_fragments.append((uri, frag))

    if not all_fragments:
        return {}

    try:
        query_emb = get_embeddings(query, embedding_model_name)
        frag_texts = [f[1] for f in all_fragments]
        frag_embs = get_embeddings(frag_texts, embedding_model_name)
    except Exception as e:
        logger.error("Failed to compute fragment embeddings: %s", e)
        return {}

    scored = []
    for i, (uri, frag) in enumerate(all_fragments):
        score = cos_compare(query_emb[0], frag_embs[i])
        scored.append((uri, frag, float(score)))

    result: Dict[str, List[str]] = {}
    scored.sort(key=lambda x: x[2], reverse=True)

    uri_counts: Dict[str, int] = {}
    selected: List[Tuple[str, str, str]] = []  # [(norm, uri, frag), ...]
    for uri, frag, score in scored:
        count = uri_counts.get(uri, 0)
        if count >= top_l:
            continue
        norm = " ".join(frag.split())
        dominated = False
        for i, (sel_norm, sel_uri, sel_frag) in enumerate(selected):
            if norm == sel_norm or (norm in sel_norm and norm != sel_norm):
                dominated = True
                break
            if sel_norm in norm and sel_norm != norm:
                selected[i] = (norm, uri, frag)
                result[sel_uri] = [f for f in result.get(sel_uri, []) if " ".join(f.split()) != sel_norm]
                if not result.get(sel_uri):
                    del result[sel_uri]
                result.setdefault(uri, []).append(frag)
                uri_counts[uri] = uri_counts.get(uri, 0) + 1
                dominated = True
                break
        if dominated:
            continue
        selected.append((norm, uri, frag))
        result.setdefault(uri, []).append(frag)
        uri_counts[uri] = count + 1

    return result