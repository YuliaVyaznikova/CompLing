# Построение эмбеддингов фрагментов текста

Разработаны функции для разбиения текста на фрагменты, генерации эмбеддингов и вычисления семантического сходства.

Эмбеддинг - это представление текста в виде числового вектора, которое позволяет применять математические операции для сравнения и поиска семантически похожих фрагментов. Для построения эмбеддингов используется модель `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, поддерживающая множество языков, включая русский.

Ниже для каждой функции приведены код, пример использования и краткое описание.

# Реализованные функции

## Функция `get_chunks`

```python
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
```

### Example usage

```python
from embeddings import get_chunks

sample_text = """
Тхэквондо ITF — это корейское боевое искусство, разработанное генералом Чой Хон Хи в 1955 году.

В тхэквондо ITF изучается 24 туля. Каждый туль назван в честь исторической личности.
"""

chunks = get_chunks(sample_text, chunk_size=512, split_by="paragraph")
print(f"Получено {len(chunks)} фрагментов:")
for i, chunk in enumerate(chunks):
    print(f"  [{i}]: {chunk[:80]}...")
```

Разбивает текст на фрагменты одним из трёх способов:
- `paragraph` - разбиение по абзацам (двойной перевод строки), сохраняет связный контекст
- `sentence` - разбиение по предложениям, объединяет предложения до достижения `chunk_size`
- `fixed` - разбиение на фрагменты фиксированного размера с перекрытием (`overlap`)

Возвращает список строк - фрагментов текста.

## Вспомогательная функция `_split_by_sentence`

```python
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
```

Разбивает текст на предложения по знакам препинания (`.!?`) и объединяет их в фрагменты до `max_size` символов. Если предложение слишком длинное, применяется `_split_fixed`.

## Вспомогательная функция `_split_fixed`

```python
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
```

Разбивает текст на фрагменты фиксированного размера. Ищет последний пробел в пределах `chunk_size`, чтобы не разрезать слова. Параметр `overlap` задаёт перекрытие между соседними фрагментами.

## Функция `get_embeddings`

```python
_cached_model = None
_cached_model_name = None


def _get_model(model_name: str):
    global _cached_model, _cached_model_name
    if _cached_model is None or _cached_model_name != model_name:
        from sentence_transformers import SentenceTransformer
        _cached_model = SentenceTransformer(model_name)
        _cached_model_name = model_name
    return _cached_model


def get_embeddings(texts: Union[str, List[str]], model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2") -> np.ndarray:
    model = _get_model(model_name)
    
    if isinstance(texts, str):
        texts = [texts]
    
    embeddings = model.encode(texts, convert_to_numpy=True)
    
    return embeddings
```

### Example usage

```python
from embeddings import get_embeddings

chunks = ["Тхэквондо — корейское боевое искусство.", "В тхэквондо изучается 24 туля."]

embeddings = get_embeddings(chunks)
print(f"Размерность эмбеддингов: {embeddings.shape}")  # (2, 768)
print(f"Тип данных: {embeddings.dtype}")  # float32

single_emb = get_embeddings("Тхэквондо — боевое искусство")
print(f"Размерность одного эмбеддинга: {single_emb.shape}")  # (1, 768)
```

Генерирует эмбеддинги для текста или списка текстов. Использует модель с размерностью вектора 768. Модель кэшируется для избежания повторной загрузки.

## Функция `cos_compare`

```python
def cos_compare(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    if embedding1.ndim == 1:
        embedding1 = embedding1.reshape(1, -1)
    if embedding2.ndim == 1:
        embedding2 = embedding2.reshape(1, -1)
    
    similarity = cosine_similarity(embedding1, embedding2)
    
    return float(similarity[0][0])
```

### Example usage

```python
from embeddings import get_embeddings, cos_compare

text1 = "Тхэквондо изучает удары ногами"
text2 = "В тхэквондо есть удары ногами"
text3 = "Погода сегодня хорошая"

emb1 = get_embeddings(text1)
emb2 = get_embeddings(text2)
emb3 = get_embeddings(text3)

sim_12 = cos_compare(emb1[0], emb2[0])
sim_13 = cos_compare(emb1[0], emb3[0])

print(f"Сходство похожих текстов: {sim_12:.4f}")  # ~0.89
print(f"Сходство разных текстов: {sim_13:.4f}")  # ~0.12
```

Вычисляет косинусное сходство между двумя векторами-эмбеддингами. Использует реализацию из `sklearn.metrics.pairwise.cosine_similarity`.

Косинусное сходство определяется формулой:

```
cos(v, w) = (w * v) / (||w|| * ||v||)
```

где `||v||` и `||w||` - длины векторов, `v * w` - скалярное произведение.

Результат — число от -1 до 1:
- `1` - максимальное сходство (векторы направлены одинаково)
- `0` - отсутствие связи (ортогональные векторы)
- `-1` - противоположность (векторы направлены в разные стороны)

## Функция `find_similar_chunks`

```python
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
```

### Example usage

```python
from embeddings import get_chunks, find_similar_chunks

sample_text = """
Тхэквондо ITF — корейское боевое искусство.
В тхэквондо изучается 24 туля.
Техника включает удары ногами и руками.
"""

chunks = get_chunks(sample_text, split_by="paragraph")

query = "Какие удары используются в тхэквондо?"
results = find_similar_chunks(query, chunks, top_k=3)

print(f"Запрос: {query}")
for r in results:
    print(f"  [{r['index']}] (sim={r['similarity']:.4f}): {r['chunk']}")
```

Выполняет семантический поиск по корпусу текстов:
1. Генерирует эмбеддинг для запроса
2. Генерирует эмбеддинги для всех фрагментов
3. Вычисляет косинусное сходство между запросом и каждым фрагментом
4. Сортирует по убыванию сходства
5. Возвращает `top_k` наиболее похожих фрагментов

Возвращает список словарей:
```python
[
    {"index": 2, "chunk": "Техника включает удары ногами...", "similarity": 0.65},
    {"index": 0, "chunk": "Тхэквондо ITF — корейское...", "similarity": 0.48},
    ...
]
```

# Демонстрация работы

Полный пример использования функций представлен в файле `usage_embeddings.py`:

```python
from embeddings import get_chunks, get_embeddings, cos_compare, find_similar_chunks

sample_text = """
Тхэквондо ITF (International Taekwon-Do Federation) — это корейское боевое искусство, разработанное генералом Чой Хон Хи в 1955 году.

В тхэквондо ITF изучается 24 туля (формальных комплексов упражнений). Каждый туль назван в честь исторической личности или события корейской истории.

Техника тхэквондо включает удары ногами, руками, блоки и стойки. Удары ногами составляют около 70% техники.

Система поясов в тхэквондо ITF включает 10 цветных поясов (гуп) от белого до красного с чёрной полосой, затем 9 данов чёрного пояса.
"""

# 1. Разбиение на фрагменты
chunks = get_chunks(sample_text, chunk_size=512, split_by="paragraph")
print(f"Получено {len(chunks)} фрагментов")

# 2. Генерация эмбеддингов
embeddings = get_embeddings(chunks)
print(f"Размерность: {embeddings.shape}")  # (N, 768)

# 3. Сравнение текстов
text1 = "Тхэквондо изучает удары ногами"
text2 = "В тхэквондо есть удары ногами"
sim = cos_compare(get_embeddings(text1)[0], get_embeddings(text2)[0])
print(f"Сходство: {sim:.4f}")  # ~0.89

# 4. Семантический поиск
query = "Какие тули изучаются в тхэквондо?"
results = find_similar_chunks(query, chunks, top_k=3)
for r in results:
    print(f"  [{r['index']}] (sim={r['similarity']:.4f}): {r['chunk'][:80]}...")
```