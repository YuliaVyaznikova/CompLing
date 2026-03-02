from typing import List, Optional, Union
import os
import logging
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TQDM_DISABLE"] = "1"

logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

_cached_model = None
_cached_model_name = None


def _get_model(model_name: str):
    global _cached_model, _cached_model_name
    if _cached_model is None or _cached_model_name != model_name:
        from sentence_transformers import SentenceTransformer
        _cached_model = SentenceTransformer(model_name)
        _cached_model_name = model_name
    return _cached_model


def get_chunks(text: str, chunk_size: int = 512, overlap: int = 50, split_by: str = "paragraph") -> List[str]:
    if not text or not text.strip():
        return []
    
    text = text.strip()
    
    if split_by == "paragraph":
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        for para in paragraphs:
            if len(para) <= chunk_size:
                chunks.append(para)
            else:
                sub_chunks = _split_by_sentence(para, chunk_size)
                chunks.extend(sub_chunks)
        return chunks
    
    elif split_by == "sentence":
        return _split_by_sentence(text, chunk_size)
    
    else:
        return _split_fixed(text, chunk_size, overlap)


def _split_by_sentence(text: str, max_size: int = 512) -> List[str]:
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_size:
            current_chunk = (current_chunk + " " + sentence).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(sentence) > max_size:
                sub = _split_fixed(sentence, max_size, 0)
                chunks.extend(sub)
            else:
                current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def _split_fixed(text: str, chunk_size: int, overlap: int) -> List[str]:
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    
    return chunks


def get_embeddings(texts: Union[str, List[str]], model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2") -> np.ndarray:
    model = _get_model(model_name)
    
    if isinstance(texts, str):
        texts = [texts]
    
    embeddings = model.encode(texts, convert_to_numpy=True)
    
    return embeddings


def cos_compare(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    if embedding1.ndim == 1:
        embedding1 = embedding1.reshape(1, -1)
    if embedding2.ndim == 1:
        embedding2 = embedding2.reshape(1, -1)
    
    similarity = cosine_similarity(embedding1, embedding2)
    
    return float(similarity[0][0])


def find_similar_chunks(query: str, chunks: List[str], top_k: int = 5, model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2") -> List[dict]:
    if not chunks:
        return []
    
    query_embedding = get_embeddings(query, model_name)
    chunk_embeddings = get_embeddings(chunks, model_name)
    
    similarities = []
    for i, chunk_emb in enumerate(chunk_embeddings):
        sim = cos_compare(query_embedding[0], chunk_emb)
        similarities.append({"index": i, "chunk": chunks[i], "similarity": sim})
    
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    return similarities[:top_k]