# CompLing

Python-репозиторий для работы с графовой базой данных Neo4j и построения эмбеддингов текстовых фрагментов.

## Структура репозитория

```
CompLing/
├── README.md                 # навигация по репозиторию и описание проекта
├── requirements.txt          # зависимости
├── realization/              # реализация
│   ├── neo4j.py              # класс Neo4jRepository (задания 1-2)
│   └── embeddings.py         # функции для эмбеддингов (задание 3)
├── usage/                    # примеры использования
│   ├── utils.py              # вспомогательные классы
│   ├── usage_neo4j.py        # пример использования методов заданий 1-2
│   ├── usage_neo4j_log.txt   # логи с neo4j
│   ├── usage_embeddings.py   # пример использования методов задания 3
│   └── usage_embeddings_log.txt  # логи с эмбеддингами
└── reports/                  # документация
    ├── report1.md            # базовые операции
    ├── report2.md            # онтология
    └── report3.md            # эмбеддинги
```

## Установка зависимостей

```bash
pip install -r requirements.txt
```

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

## Функционал

### Задание №1: Базовые операции с графом

- `create_node`, `get_node_by_uri`, `update_node`, `delete_node_by_uri`
- `create_arc`, `delete_arc_by_id`
- `get_all_nodes_and_arcs`, `get_nodes_by_labels`
- `run_custom_query` - произвольные Cypher-запросы

### Задание №2: Работа с онтологией

- Классы: `create_class`, `get_class`, `update_class`, `delete_class`, `get_class_parents`, `get_class_children`
- Объекты: `create_object`, `get_object`, `update_object`, `delete_object`, `get_class_objects`
- Атрибуты: `add_class_attribute`, `delete_class_attribute`, `add_class_object_attribute`, `delete_class_object_attribute`
- Сигнатура: `collect_signature` - сбор всех свойств класса и его родителей

### Задание №3: Построение эмбеддингов

- `get_chunks` - разбиение текста на фрагменты (по абзацам, предложениям, фиксированный размер)
- `get_embeddings` - генерация эмбеддингов с использованием sentence-transformers
- `cos_compare` - вычисление косинусного сходства между двумя эмбеддингами
- `find_similar_chunks` - семантический поиск по корпусу текстов

## Документация

- [reports/report1.md](reports/report1.md) - описание методов задания №1
- [reports/report2.md](reports/report2.md) - описание методов задания №2
- [reports/report3.md](reports/report3.md) - описание методов задания №3