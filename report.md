# Разработка драйвера для графовой базы данных Neo4j

Разработан класс `Neo4jRepository`, реализующий методы из задания `task.txt` для работы с графовой бд Neo4j.

В репозитории для узлов основным идентификатором используется поле `uri` (как указано в задании), а для связей используется `elementId(r)` (поле `id` в `TArc`) для удобства удаления связи.

Ниже для каждого метода приведены код метода, пример использования, краткое описание.

Во всех примерах предполагается, что создан объект `config`:

```python
from func import Neo4jConfig, Neo4jRepository

config = Neo4jConfig(
    uri="bolt://127.0.0.1:7687",
    user="neo4j",
    password="<пароль_из_neo4j_desktop>",
)
```

# Реализованные методы

## Метод `generate_random_string`

```python
def generate_random_string(self, length: int = 12, namespace_title: str = "ontology") -> str:
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(random.choice(alphabet) for _ in range(length))
    return f"http://{namespace_title}.com/{random_part}"
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    uri = repo.generate_random_string(length=8, namespace_title="myont")
    print(uri)
```

Генерирует строку-URI вида `http://<namespace_title>.com/<random_string>`. Обычно используется при создании узла, если `uri` не задан.

## Метод `collect_node`

```python
def collect_node(self, node: Any) -> TNode:
    labels = list(getattr(node, "labels", []))
    props = dict(getattr(node, "_properties", {}))
    return {
        "uri": str(props.get("uri", "")),
        "description": str(props.get("description", "")),
        "label": str(labels[0]) if labels else "",
    }
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    node = repo.create_node({"label": "Entity", "description": "test"})
    # node уже в формате TNode, т.к. create_node внутри вызывает collect_node
    print(node["uri"], node["label"], node["description"])
```

Преобразует объект `neo4j.graph.Node` в словарь `TNode` (URI + описание + первая метка узла).

## Метод `collect_arc`

```python
def collect_arc(self, arc: Any) -> TArc:
    if isinstance(arc, dict) and "rel" in arc:
        rel = arc.get("rel")
        return {
            "id": str(arc.get("id", getattr(rel, "element_id", ""))),
            "uri": str(getattr(rel, "type", "")),
            "node_uri_from": str(arc.get("node_uri_from", "")),
            "node_uri_to": str(arc.get("node_uri_to", "")),
        }

    start_uri = ""
    end_uri = ""
    if hasattr(arc, "start_node") and arc.start_node is not None:
        try:
            start_uri = str(dict(arc.start_node).get("uri", ""))
        except Exception:
            start_uri = ""

    if hasattr(arc, "end_node") and arc.end_node is not None:
        try:
            end_uri = str(dict(arc.end_node).get("uri", ""))
        except Exception:
            end_uri = ""

    return {
        "id": str(getattr(arc, "element_id", "")),
        "uri": str(getattr(arc, "type", "")),
        "node_uri_from": str(start_uri),
        "node_uri_to": str(end_uri),
    }
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    n1 = repo.create_node({"label": "Entity", "description": "A"})
    n2 = repo.create_node({"label": "Entity", "description": "B"})
    arc = repo.create_arc(n1["uri"], n2["uri"], rel_type="RELATED")
    # arc уже в формате TArc, т.к. create_arc внутри вызывает collect_arc
    print(arc["id"], arc["uri"], arc["node_uri_from"], arc["node_uri_to"])
```

Преобразует объект связи Neo4j (или словарь-обёртку с `rel`, `id`, `node_uri_from/to`) в словарь `TArc`.

## Метод `run_custom_query`

```python
def run_custom_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    with self._driver.session(**self._session_kwargs()) as session:
        result = session.run(query, params or {})
        return [dict(r) for r in result]
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    rows = repo.run_custom_query("MATCH (n) RETURN count(n) AS cnt")
    print(rows)  # например: [{'cnt': 10}]
```

Выполняет произвольный Cypher-запрос и возвращает результат как список словарей (каждая запись `Record` преобразуется в `dict`).

## Метод `get_all_nodes_and_arcs`

```python
def get_all_nodes_and_arcs(self) -> Tuple[List[TNode], List[TArc]]:
    cypher_nodes = "MATCH (n) RETURN n AS node"
    cypher_arcs = "MATCH (a)-[r]->(b) RETURN elementId(r) AS id, r AS rel, a.uri AS node_uri_from, b.uri AS node_uri_to"

    nodes_by_uri: Dict[str, TNode] = {}
    arcs_by_id: Dict[str, TArc] = {}

    with self._driver.session(**self._session_kwargs()) as session:
        for record in session.run(cypher_nodes):
            n = record.get("node")
            if n is None:
                continue
            node_dict = self.collect_node(n)
            if node_dict["uri"]:
                nodes_by_uri[node_dict["uri"]] = node_dict

        for record in session.run(cypher_arcs):
            rel = record.get("rel")
            if rel is None:
                continue
            arc_dict = self.collect_arc(
                {
                    "id": record.get("id", ""),
                    "rel": rel,
                    "node_uri_from": record.get("node_uri_from", ""),
                    "node_uri_to": record.get("node_uri_to", ""),
                }
            )
            if arc_dict["id"]:
                arcs_by_id[arc_dict["id"]] = arc_dict

    return list(nodes_by_uri.values()), list(arcs_by_id.values())
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    nodes, arcs = repo.get_all_nodes_and_arcs()
    print(f"Узлов: {len(nodes)}")
    print(f"Дуг: {len(arcs)}")
    # nodes: List[TNode], arcs: List[TArc]
```

Возвращает все узлы и все связи из бд. Используются два запроса (отдельный запрос для узлов и отдельный запрос для дуг), после чего результаты приводятся к `TNode`/`TArc`.

## Метод `get_nodes_by_labels`

```python
def get_nodes_by_labels(self, labels: Sequence[str]) -> List[TNode]:
    if not labels:
        return []

    cypher = "MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) RETURN n AS node"

    nodes: List[TNode] = []
    with self._driver.session(**self._session_kwargs()) as session:
        for record in session.run(cypher, {"labels": list(labels)}):
            n = record.get("node")
            if n is None:
                continue
            nodes.append(self.collect_node(n))
    return nodes
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    nodes = repo.get_nodes_by_labels(["Person", "Company"])
    print(len(nodes))
    if nodes:
        print(nodes[0])
```

Возвращает список узлов, у которых есть хотя бы одна метка из `labels`. Если `labels` пустой, возвращается пустой список.

## Метод `get_node_by_uri`

```python
def get_node_by_uri(self, uri: str) -> Optional[TNode]:
    cypher = "MATCH (n {uri: $uri}) RETURN n AS node LIMIT 1"
    with self._driver.session(**self._session_kwargs()) as session:
        record = session.run(cypher, {"uri": uri}).single()
        if not record:
            return None
        node = record.get("node")
        if node is None:
            return None
        return self.collect_node(node)
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    created = repo.create_node({"label": "Entity", "description": "X"})
    found = repo.get_node_by_uri(created["uri"])
    print(found)  # либо TNode, либо None
```

Ищет узел по `uri`. Возвращает `TNode`, если узел найден, иначе `None`.

## Метод `create_node`

```python
def create_node(self, params: Dict[str, Any]) -> TNode:
    label = str(params.get("label", ""))
    if not label:
        raise ValueError("label is required")

    uri = str(params.get("uri") or self.generate_random_string())
    props: Dict[str, Any] = {"uri": uri}

    if "description" in params:
        props["description"] = params.get("description")

    for k, v in params.items():
        if k in {"label", "uri"}:
            continue
        props[k] = v

    cypher = f"CREATE (n:`{label}` $props) RETURN n AS node"

    with self._driver.session(**self._session_kwargs()) as session:
        record = session.run(cypher, {"props": props}).single()
        if not record or record.get("node") is None:
            raise RuntimeError("Failed to create node")
        return self.collect_node(record.get("node"))
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    node = repo.create_node(
        {
            "label": "Person",
            "description": "Иван Иванов",
            "age": 30,
            "skills": ["Python", "Neo4j"],
        }
    )
    print(node)
```

Создаёт новый узел с меткой `label` и любыми свойствами из `params` (кроме `label`). Если `uri` не передан, он генерируется автоматически. Возвращается созданный узел в формате `TNode`.

## Метод `create_arc`

```python
def create_arc(self, node1_uri: str, node2_uri: str, rel_type: str = "RELATED") -> TArc:
    if not rel_type:
        rel_type = "RELATED"

    cypher = (
        "MATCH (a {uri: $from_uri}), (b {uri: $to_uri}) "
        f"CREATE (a)-[r:`{rel_type}`]->(b) "
        "RETURN elementId(r) AS id, r AS rel, a.uri AS node_uri_from, b.uri AS node_uri_to"
    )

    with self._driver.session(**self._session_kwargs()) as session:
        record = session.run(cypher, {"from_uri": node1_uri, "to_uri": node2_uri}).single()
        if not record or record.get("rel") is None:
            raise RuntimeError("Failed to create arc (relationship). Check that both nodes exist.")
        return self.collect_arc(
            {
                "id": record.get("id", ""),
                "rel": record.get("rel"),
                "node_uri_from": record.get("node_uri_from", ""),
                "node_uri_to": record.get("node_uri_to", ""),
            }
        )
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    a = repo.create_node({"label": "Entity", "description": "A"})
    b = repo.create_node({"label": "Entity", "description": "B"})
    arc = repo.create_arc(a["uri"], b["uri"], rel_type="RELATED")
    print(arc)
```

Создаёт направленную связь типа `rel_type` от узла с `node1_uri` к узлу с `node2_uri`. Возвращает информацию о связи в `TArc` (включая `id = elementId`).

## Метод `delete_node_by_uri`

```python
def delete_node_by_uri(self, uri: str) -> bool:
    cypher = "MATCH (n {uri: $uri}) DETACH DELETE n RETURN count(n) AS deleted"
    with self._driver.session(**self._session_kwargs()) as session:
        record = session.run(cypher, {"uri": uri}).single()
        if not record:
            return False
        return int(record.get("deleted", 0)) > 0
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    node = repo.create_node({"label": "Entity", "description": "to delete"})
    ok = repo.delete_node_by_uri(node["uri"])
    print(ok)  # True, если узел был найден и удалён
```

Удаляет узел по `uri` вместе со всеми его связями (`DETACH DELETE`). Возвращает `True`, если удаление произошло.

## Метод `delete_arc_by_id`

```python
def delete_arc_by_id(self, arc_id: str) -> bool:
    cypher = "MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r RETURN count(r) AS deleted"
    with self._driver.session(**self._session_kwargs()) as session:
        record = session.run(cypher, {"id": str(arc_id)}).single()
        if not record:
            return False
        return int(record.get("deleted", 0)) > 0
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    a = repo.create_node({"label": "Entity", "description": "A"})
    b = repo.create_node({"label": "Entity", "description": "B"})
    arc = repo.create_arc(a["uri"], b["uri"], rel_type="RELATED")
    ok = repo.delete_arc_by_id(arc["id"])
    print(ok)  # True, если связь была удалена
```

Удаляет связь по её `elementId` (поле `id` в `TArc`). Возвращает `True`, если связь была найдена и удалена.

## Метод `update_node`

```python
def update_node(self, uri: str, params: Dict[str, Any]) -> Optional[TNode]:
    if not params:
        return self.get_node_by_uri(uri)

    props: Dict[str, Any] = {}
    for k, v in params.items():
        if k in {"uri", "label"}:
            continue
        props[k] = v

    if not props:
        return self.get_node_by_uri(uri)

    cypher = "MATCH (n {uri: $uri}) SET n += $props RETURN n AS node"

    with self._driver.session(**self._session_kwargs()) as session:
        record = session.run(cypher, {"uri": uri, "props": props}).single()
        if not record or record.get("node") is None:
            return None
        return self.collect_node(record.get("node"))
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    node = repo.create_node({"label": "Person", "description": "Иван", "age": 30})
    updated = repo.update_node(node["uri"], {"age": 31, "status": "active"})
    print(updated)
```

Обновляет свойства узла по `uri` (добавляет/заменяет свойства через `SET n += $props`). Поля `uri` и `label` намеренно игнорируются. Если узел не найден, возвращается `None`.

## Дополнительные методы форматирования (`transform_labels`, `transform_props`)

Эти методы могут использоваться при формировании Cypher-строк.

```python
def transform_labels(self, labels: Sequence[str], separator: str = ":") -> str:
    if not labels:
        return "``"
    return separator.join(f"`{l}`" for l in labels)
```

```python
def transform_props(self, props: Dict[str, Any]) -> str:
    if not props:
        return ""

    def _format_value(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(_format_value(x) for x in v) + "]"
        return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"

    parts = []
    for k, v in props.items():
        parts.append(f"`{k}`: {_format_value(v)}")
    return "{" + ", ".join(parts) + "}"
```