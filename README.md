# CompLing

Репозиторий для работы с графовой базой данных Neo4j, построения эмбеддингов текстовых фрагментов и RAG-системы на основе онтологии

## Подключение к бд

```python
from neo4j import Neo4jConfig, Neo4jRepository

config = Neo4jConfig(
    uri="bolt://127.0.0.1:7687",
    user="neo4j",
    password="<пароль>",
)

with Neo4jRepository(config) as repo:
    # тут работа с репозиторием
    pass
```

## Использование эмбеддингов

```python
from embeddings import get_chunks, get_embeddings, cos_compare, find_similar_chunks

# разбиение текста на фрагменты
chunks = get_chunks(text, split_by="paragraph")

# генерация эмбеддингов
embeddings = get_embeddings(chunks)

# семантический поиск
results = find_similar_chunks("запрос", chunks, top_k=5)
```

## RAG на основе онтологии

Трёхфазная система генерации ответов по онтологии (на примере онтологии по популярным детективным фильмам):
1. На этапе индексации каждый узел онтологии преобразуется в текстовый фрагмент с названием, типом, связями и атрибутами, после чего для него вычисляется эмбеддинг. 
2. Далее выполняется гибридный поиск (семантическое сходство + IDF-взвешенные ключевые слова), который находит top-N наиболее релевантных узлов. Их описания передаются в LLM, которая даёт начальный ответ. 
3. Затем этот ответ векторизуется, по нему находятся top-M дополнительных узлов, не пересекающихся с первой выборкой, и все N+M фрагментов отправляются в LLM для финального ответа. Если score ретривала низкий, система сообщает, что вопрос не относится к онтологии фильмов.

```python
from realization.ontology_rag import OntologyRAG

rag = OntologyRAG(
    ontology_path="ontology_all_films.json",
    model_name="qwen2.5:3b",
)
rag.index()
result = rag.answer("Кого убил лорд Блэквуд?", top_n=10, top_m=3)
print(result["final_answer"])
```

#### запустить можно на готовых вопросах либо в интерактивном режиме

```bash
# демо с тестовыми запросами
python CompLing/usage/demo_rag.py

# интерактивный режим
python CompLing/usage/ask_rag.py
```

## Функционал

### Базовые операции с графом

- `create_node`, `get_node_by_uri`, `update_node`, `delete_node_by_uri`
- `create_arc`, `delete_arc_by_id`
- `get_all_nodes_and_arcs`, `get_nodes_by_labels`
- `run_custom_query` - произвольные Cypher-запросы

### Работа с онтологией

- Классы: `create_class`, `get_class`, `update_class`, `delete_class`, `get_class_parents`, `get_class_children`
- Объекты: `create_object`, `get_object`, `update_object`, `delete_object`, `get_class_objects`
- Атрибуты: `add_class_attribute`, `delete_class_attribute`, `add_class_object_attribute`, `delete_class_object_attribute`
- Сигнатура: `collect_signature` - сбор всех свойств класса и его родителей

### Построение эмбеддингов

- `get_chunks` - разбиение текста на фрагменты (по абзацам, предложениям, фиксированный размер)
- `get_embeddings` - генерация эмбеддингов с использованием sentence-transformers
- `cos_compare` - вычисление косинусного сходства между двумя эмбеддингами
- `find_similar_chunks` - семантический поиск по корпусу текстов