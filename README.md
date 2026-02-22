# CompLing

Python-репозиторий для работы с графовой базой данных Neo4j: базовые CRUD-операции и редактирование онтологии предметной области.

## Структура репозитория

```
CompLing/
├── func.py               # Класс Neo4jRepository
├── usage.py              # Примеры использования всех методов
├── usage_log.txt         # Как выглядит пример использования
├── requirements.txt      # Зависимости (neo4j>=5.0.0)
├── report1.md            # Отчёт по заданию №1 (базовые операции)
├── report2.md            # Отчёт по заданию №2 (онтология)
└── README.md             # Навигация по репозиторию
```

## Установка

```bash
pip install -r requirements.txt
```

## Подключение

```python
from neo4j_repository import Neo4jConfig, Neo4jRepository

config = Neo4jConfig(
    uri="bolt://127.0.0.1:7687",
    user="neo4j",
    password="<пароль>",
)

with Neo4jRepository(config) as repo:
    # Работа с репозиторием
    pass
```

## Возможности

### Задание №1: Базовые операции с графом

- `create_node`, `get_node_by_uri`, `update_node`, `delete_node_by_uri`
- `create_arc`, `delete_arc_by_id`
- `get_all_nodes_and_arcs`, `get_nodes_by_labels`
- `run_custom_query` — произвольные Cypher-запросы

### Задание №2: Работа с онтологией

- **Классы:** `create_class`, `get_class`, `update_class`, `delete_class`, `get_class_parents`, `get_class_children`
- **Объекты:** `create_object`, `get_object`, `update_object`, `delete_object`, `get_class_objects`
- **Атрибуты:** `add_class_attribute`, `delete_class_attribute`, `add_class_object_attribute`, `delete_class_object_attribute`
- **Сигнатура:** `collect_signature` — сбор всех свойств класса и его родителей

## Документация

- [report1.md](report1.md) — описание методов задания №1
- [report2.md](report2.md) — описание методов задания №2