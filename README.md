# CompLing

Python-репозиторий для работы с графовой базой данных Neo4j (на данный момент реализованы базовые CRUD-операции и редактирование онтологии предметной области)

## Структура репозитория

```
CompLing/
├── README.md                 # навигация по репозиторию и описание проекта
├── realization/              # реализация
│   ├── func.py               # класс Neo4jRepository
│   ├── usage.py              # пример использования всех методов
│   ├── usage_log.txt         # как выглядит пример использования
│   ├── requirements.txt      # зависимости
│   └── .gitignore
└── reports/                  # описание функционала
    ├── report1.md            # базовые операции
    └── report2.md            # онтология
```

## Установка зависимостей

```bash
cd realization
pip install -r requirements.txt
```

## Подключение к бд

```python
from func import Neo4jConfig, Neo4jRepository

config = Neo4jConfig(
    uri="bolt://127.0.0.1:7687",
    user="neo4j",
    password="<пароль>",
)

with Neo4jRepository(config) as repo:
    # тут работа с репозиторием
    pass
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

## Документация

- [reports/report1.md](reports/report1.md) — описание методов задания №1
- [reports/report2.md](reports/report2.md) — описание методов задания №2
