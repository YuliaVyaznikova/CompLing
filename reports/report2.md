# Разработка репозитория для редактирования онтологии предметной области

Детализирован класс `Neo4jRepository`, реализующий методы для работы с онтологией в Neo4j.

Онтология строится по следующей методологии:
- Классы имеют метки `"Class"` и `uri` класса, а также свойства `uri`, `title`, `description`
- Объекты имеют метки `"Object"`, `uri` класса и `uri` объекта, а также свойства `uri`, `title`, `description`
- DatatypeProperty - узлы с меткой `"DatatypeProperty"`, свойства `uri`, `title` (атрибуты класса)
- ObjectProperty - узлы с меткой `"ObjectProperty"`, свойства `uri`, `title` (связи между объектами разных классов)
- Связи: `SUBCLASSOF` (наследование классов), `INSTANCEOF` (объект-класс), `DOMAIN` (свойство-класс), `RANGE` (ObjectProperty-целевой класс)

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

# Реализованные методы для работы с онтологией

## Метод `get_ontology`

```python
def get_ontology(self) -> Tuple[List[TNode], List[TArc]]:
    return self.get_all_nodes_and_arcs()
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    nodes, arcs = repo.get_ontology()
    print(f"Узлов в онтологии: {len(nodes)}")
    print(f"Связей в онтологии: {len(arcs)}")
```

Возвращает все узлы и связи из базы данных. Является обёрткой над `get_all_nodes_and_arcs`.

## Метод `get_ontology_parent_classes`

```python
def get_ontology_parent_classes(self) -> List[TNode]:
    cypher = "MATCH (c:`Class`) WHERE NOT (c)-[:SUBCLASSOF]->() RETURN c AS node"
    with self._driver.session(**self._session_kwargs()) as session:
        return [self.collect_node(record.get("node")) for record in session.run(cypher)]
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    parent_classes = repo.get_ontology_parent_classes()
    print("Корневые классы:", [c["title"] for c in parent_classes])
```

Возвращает список классов, у которых нет родителей (корневые классы онтологии).

## Метод `get_class`

```python
def get_class(self, uri: str) -> Optional[TNode]:
    node = self.get_node_by_uri(uri)
    if node and node["label"] == "Class":
        return node
    return None
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    cls = repo.get_class("http://ontology.com/abc123")
    if cls:
        print("Класс найден:", cls["title"])
```

Возвращает класс по его `uri`, если узел существует и имеет метку `"Class"`. Иначе возвращает `None`.

## Метод `get_class_parents`

```python
def get_class_parents(self, uri: str) -> List[TNode]:
    cypher = "MATCH (c {uri: $uri})-[:SUBCLASSOF]->(p:`Class`) RETURN p AS node"
    with self._driver.session(**self._session_kwargs()) as session:
        return [self.collect_node(record.get("node")) for record in session.run(cypher, {"uri": uri})]
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    parents = repo.get_class_parents(child_class_uri)
    print("Родители класса:", [p["title"] for p in parents])
```

Возвращает список родительских классов для указанного класса (по связям `SUBCLASSOF`).

## Метод `get_class_children`

```python
def get_class_children(self, uri: str) -> List[TNode]:
    cypher = "MATCH (child:`Class`)-[:SUBCLASSOF]->(c {uri: $uri}) RETURN child AS node"
    with self._driver.session(**self._session_kwargs()) as session:
        return [self.collect_node(record.get("node")) for record in session.run(cypher, {"uri": uri})]
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    children = repo.get_class_children(parent_class_uri)
    print("Дочерние классы:", [c["title"] for c in children])
```

Возвращает список дочерних классов (потомков) для указанного класса.

## Метод `get_class_objects`

```python
def get_class_objects(self, class_uri: str) -> List[TNode]:
    cypher = "MATCH (o:`Object`)-[:INSTANCEOF]->(c {uri: $class_uri}) RETURN o AS node"
    with self._driver.session(**self._session_kwargs()) as session:
        return [self.collect_node(record.get("node")) for record in session.run(cypher, {"class_uri": class_uri})]
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    objects = repo.get_class_objects(class_uri)
    print("Объекты класса:", [o["title"] for o in objects])
```

Возвращает список объектов, принадлежащих указанному классу (по связям `INSTANCEOF`).

## Метод `update_class`

```python
def update_class(self, uri: str, title: Optional[str] = None, description: Optional[str] = None) -> Optional[TNode]:
    params = {}
    if title is not None:
        params["title"] = title
    if description is not None:
        params["description"] = description
    return self.update_node(uri, params)
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    updated = repo.update_class(class_uri, title="Новое название", description="Новое описание")
    print("Обновлённый класс:", updated)
```

Обновляет `title` и/или `description` класса. Возвращает обновлённый узел или `None`, если класс не найден.

## Метод `create_class`

```python
def create_class(self, title: str, description: str = "", parent_uri: Optional[str] = None) -> TNode:
    uri = self.generate_random_string()
    params = {"label": "Class", "uri": uri, "title": title, "description": description}
    node = self.create_node(params)
    if parent_uri:
        self.create_arc(node["uri"], parent_uri, "SUBCLASSOF")
    return node
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    parent = repo.create_class("Person", "Человек")
    child = repo.create_class("Student", "Студент", parent_uri=parent["uri"])
    print("Создан родительский класс:", parent)
    print("Создан дочерний класс:", child)
```

Создаёт новый класс с указанными `title` и `description`. Если задан `parent_uri`, создаётся связь `SUBCLASSOF` к родительскому классу.

## Метод `delete_class`

```python
def delete_class(self, uri: str) -> bool:
    with self._driver.session(**self._session_kwargs()) as session:
        cypher_desc = "MATCH (desc:`Class`)-[:SUBCLASSOF*0..]->(c {uri: $uri}) RETURN distinct desc.uri AS uri"
        desc_uris = [r["uri"] for r in session.run(cypher_desc, {"uri": uri})]
        if not desc_uris:
            return False
        cypher_objs = "MATCH (o:`Object`)-[:INSTANCEOF]->(c:`Class` WHERE c.uri IN $class_uris) RETURN o.uri AS uri"
        obj_uris = [r["uri"] for r in session.run(cypher_objs, {"class_uris": desc_uris})]
    for o_uri in obj_uris:
        self.delete_node_by_uri(o_uri)
    for d_uri in desc_uris:
        self.delete_node_by_uri(d_uri)
    return True
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    deleted = repo.delete_class(parent_class_uri)
    print("Класс и все его потомки удалены:", deleted)
```

Удаляет класс вместе со всеми его потомками (по иерархии `SUBCLASSOF`), а также все объекты этих классов. Каскадное удаление.

## Метод `add_class_attribute`

```python
def add_class_attribute(self, class_uri: str, title: str) -> TNode:
    if not self.get_node_by_uri(class_uri):
        raise ValueError("Class not found")
    prop_uri = self.generate_random_string()
    prop = self.create_node({"label": "DatatypeProperty", "uri": prop_uri, "title": title})
    self.create_arc(prop["uri"], class_uri, "DOMAIN")
    return prop
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    attr_name = repo.add_class_attribute(class_uri, "name")
    attr_age = repo.add_class_attribute(class_uri, "age")
    print("Добавлен атрибут name:", attr_name)
    print("Добавлен атрибут age:", attr_age)
```

Создаёт узел `DatatypeProperty` с указанным `title` и связывает его с классом через `DOMAIN`. Используется для определения атрибутов класса.

## Метод `delete_class_attribute`

```python
def delete_class_attribute(self, prop_uri: str) -> bool:
    node = self.get_node_by_uri(prop_uri)
    if not node or node["label"] != "DatatypeProperty":
        return False
    return self.delete_node_by_uri(prop_uri)
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    deleted = repo.delete_class_attribute(prop_uri)
    print("Атрибут удалён:", deleted)
```

Удаляет `DatatypeProperty` по его `uri`. Возвращает `True`, если узел существовал и был удалён.

## Метод `add_class_object_attribute`

```python
def add_class_object_attribute(self, class_uri: str, attr_name: str, range_class_uri: str) -> TNode:
    if not self.get_node_by_uri(class_uri) or not self.get_node_by_uri(range_class_uri):
        raise ValueError("Class not found")
    prop_uri = self.generate_random_string()
    prop = self.create_node({"label": "ObjectProperty", "uri": prop_uri, "title": attr_name})
    self.create_arc(prop["uri"], class_uri, "DOMAIN")
    self.create_arc(prop["uri"], range_class_uri, "RANGE")
    return prop
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    obj_attr = repo.add_class_object_attribute(person_class_uri, "teaches", student_class_uri)
    print("Добавлена объектная связь:", obj_attr)
```

Создаёт узел `ObjectProperty` с указанным `title`, связывает его с исходным классом через `DOMAIN` и с целевым классом через `RANGE`. Определяет связь между объектами разных классов.

## Метод `delete_class_object_attribute`

```python
def delete_class_object_attribute(self, object_property_uri: str) -> bool:
    node = self.get_node_by_uri(object_property_uri)
    if not node or node["label"] != "ObjectProperty":
        return False
    return self.delete_node_by_uri(object_property_uri)
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    deleted = repo.delete_class_object_attribute(prop_uri)
    print("Объектная связь удалена:", deleted)
```

Удаляет `ObjectProperty` по его `uri`. Возвращает `True`, если узел существовал и был удалён.

## Метод `add_class_parent`

```python
def add_class_parent(self, parent_uri: str, target_uri: str):
    if not self.get_node_by_uri(parent_uri) or not self.get_node_by_uri(target_uri):
        raise ValueError("Class not found")
    self.create_arc(target_uri, parent_uri, "SUBCLASSOF")
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    repo.add_class_parent(parent_class_uri, child_class_uri)
    print("Родитель добавлен к классу")
```

Добавляет связь `SUBCLASSOF` от целевого класса к родительскому. Классы должны существовать.

## Метод `get_object`

```python
def get_object(self, uri: str) -> Optional[TNode]:
    node = self.get_node_by_uri(uri)
    if node and node["label"] == "Object":
        return node
    return None
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    obj = repo.get_object(object_uri)
    if obj:
        print("Объект найден:", obj["title"])
```

Возвращает объект по его `uri`, если узел существует и имеет метку `"Object"`. Иначе возвращает `None`.

## Метод `delete_object`

```python
def delete_object(self, uri: str) -> bool:
    if not self.get_object(uri):
        return False
    return self.delete_node_by_uri(uri)
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    deleted = repo.delete_object(object_uri)
    print("Объект удалён:", deleted)
```

Удаляет объект по его `uri`. Возвращает `True`, если объект существовал и был удалён.

## Метод `create_object`

```python
def create_object(self, class_uri: str, title: str, description: str = "", properties: Dict[str, Any] = {}, object_properties: List[Dict[str, Any]] = []) -> TNode:
    if not self.get_class(class_uri):
        raise ValueError("Class not found")
    signature = self.collect_signature(class_uri)
    param_uris = {p["uri"] for p in signature["params"]}
    for k in properties:
        if k not in param_uris:
            raise ValueError(f"Unknown property {k}")

    obj_param_uris = {p["uri"] for p in signature["obj_params"]}
    for op in object_properties:
        relation_uri = op.get("relation_uri", "")
        if relation_uri not in obj_param_uris:
            raise ValueError(f"Unknown object property {relation_uri}")
        if not self.get_node_by_uri(op.get("obj_uri", "")):
            raise ValueError(f"Target object not found: {op.get('obj_uri', '')}")

    uri = self.generate_random_string()
    params = {"label": "Object", "title": title, "description": description, "uri": uri}
    params.update(properties)
    node = self.create_node(params)
    self.create_arc(uri, class_uri, "INSTANCEOF")

    for op in object_properties:
        obj_uri = op.get("obj_uri", "")
        relation_uri = op.get("relation_uri", "")
        direction = op.get("direction", 1)
        rel_node = self.get_node_by_uri(relation_uri)
        rel_type = rel_node["title"] if rel_node else "RELATED"
        if direction == 1:
            self.create_arc(uri, obj_uri, rel_type)
        else:
            self.create_arc(obj_uri, uri, rel_type)

    return node
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    person_class = repo.create_class("Person", "Человек")
    city_class = repo.create_class("City", "Город")

    attr_name = repo.add_class_attribute(person_class["uri"], "name")
    lives_in = repo.add_class_object_attribute(person_class["uri"], "lives_in", city_class["uri"])

    moscow = repo.create_object(city_class["uri"], "Москва", "Столица России")

    obj = repo.create_object(
        person_class["uri"],
        title="Маша",
        description="Тестовый объект",
        properties={attr_name["uri"]: "Мария"},
        object_properties=[
            {
                "destination_class": city_class["uri"],
                "obj_uri": moscow["uri"],
                "direction": 1,
                "relation_uri": lives_in["uri"]
            }
        ]
    )
    print("Создан объект:", obj)
```

Создаёт объект указанного класса. Параметры:
- `properties` - словарь `{datatype_property_uri: value}` для атрибутов объекта
- `object_properties` - список связей с другими объектами, каждый элемент содержит:
  - `destination_class` - URI целевого класса
  - `obj_uri` - URI целевого объекта
  - `direction` - направление связи: `1` (объект -> цель) или `-1` (цель -> объект)
  - `relation_uri` - URI ObjectProperty, определяющей тип связи

Автоматически создаётся связь `INSTANCEOF` к классу и связи к другим объектам.

## Метод `update_object`

```python
def update_object(self, uri: str, title: Optional[str] = None, description: Optional[str] = None, properties: Dict[str, Any] = {}, object_properties: Optional[List[Dict[str, Any]]] = None) -> Optional[TNode]:
    obj = self.get_object(uri)
    if not obj:
        return None
    with self._driver.session(**self._session_kwargs()) as session:
        cypher_class = "MATCH (o {uri: $uri})-[:INSTANCEOF]->(c) RETURN c.uri AS class_uri"
        record = session.run(cypher_class, {"uri": uri}).single()
        class_uri = record["class_uri"] if record else None
        if not class_uri:
            raise RuntimeError("No class for object")
        signature = self.collect_signature(class_uri)
        param_uris = {p["uri"] for p in signature["params"]}
        for k in properties:
            if k not in param_uris:
                raise ValueError(f"Unknown property {k}")

        if object_properties is not None:
            obj_param_uris = {p["uri"] for p in signature["obj_params"]}
            for op in object_properties:
                relation_uri = op.get("relation_uri", "")
                if relation_uri not in obj_param_uris:
                    raise ValueError(f"Unknown object property {relation_uri}")
                if not self.get_node_by_uri(op.get("obj_uri", "")):
                    raise ValueError(f"Target object not found: {op.get('obj_uri', '')}")

            cypher_current = """
            MATCH (o {uri: $uri})-[r]-(target)
            WHERE target:`Object`
            RETURN type(r) AS rel_type, target.uri AS target_uri, elementId(r) AS arc_id,
                   CASE WHEN startNode(r).uri = $uri THEN 1 ELSE -1 END AS direction
            """
            current_rels = list(session.run(cypher_current, {"uri": uri}))

            new_rels_set = set()
            for op in object_properties:
                key = (op.get("relation_uri", ""), op.get("obj_uri", ""), op.get("direction", 1))
                new_rels_set.add(key)

            for rel in current_rels:
                rel_type = rel["rel_type"]
                target_uri = rel["target_uri"]
                arc_id = rel["arc_id"]
                rel_direction = rel["direction"]
                rel_node = None
                for p in signature["obj_params"]:
                    if p["title"] == rel_type:
                        rel_node = p
                        break
                if rel_node:
                    key = (rel_node["uri"], target_uri, rel_direction)
                    if key not in new_rels_set:
                        self.delete_arc_by_id(arc_id)

            for op in object_properties:
                obj_uri = op.get("obj_uri", "")
                relation_uri = op.get("relation_uri", "")
                direction = op.get("direction", 1)
                rel_node = self.get_node_by_uri(relation_uri)
                rel_type = rel_node["title"] if rel_node else "RELATED"
                if direction == 1:
                    cypher_check = """
                    MATCH (o {uri: $uri})-[r]->(target {uri: $target_uri})
                    WHERE type(r) = $rel_type
                    RETURN count(r) AS cnt
                    """
                    check = session.run(cypher_check, {"uri": uri, "target_uri": obj_uri, "rel_type": rel_type}).single()
                    if check and check["cnt"] == 0:
                        self.create_arc(uri, obj_uri, rel_type)
                else:
                    cypher_check = """
                    MATCH (target {uri: $target_uri})-[r]->(o {uri: $uri})
                    WHERE type(r) = $rel_type
                    RETURN count(r) AS cnt
                    """
                    check = session.run(cypher_check, {"uri": uri, "target_uri": obj_uri, "rel_type": rel_type}).single()
                    if check and check["cnt"] == 0:
                        self.create_arc(obj_uri, uri, rel_type)

        params = {}
        if title is not None:
            params["title"] = title
        if description is not None:
            params["description"] = description
        params.update(properties)
        return self.update_node(uri, params)
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    # Маша переезжает из Москвы в Санкт-Петербург
    spb = repo.create_object(city_class["uri"], "Санкт-Петербург", "Культурная столица")

    updated = repo.update_object(
        obj["uri"],
        title="Мария",
        properties={attr_name["uri"]: "Мария Ивановна"},
        object_properties=[
            {
                "destination_class": city_class["uri"],
                "obj_uri": spb["uri"],
                "direction": 1,
                "relation_uri": lives_in["uri"]
            }
        ]
    )
    print("Обновлённый объект:", updated)
```

Обновляет `title`, `description`, свойства объекта и его связи с другими объектами. При указании `object_properties`:
- Связи, которых нет в новом списке, удаляются
- Новые связи, которых ещё не было, создаются
- `direction` учитывается при проверке и создании связей

## Метод `collect_signature`

```python
def collect_signature(self, class_uri: str) -> Dict[str, List[Dict[str, Any]]]:
    if not self.get_class(class_uri):
        raise ValueError("Class not found")
    query_datatype = """
    MATCH (n {uri: $uri})-[:SUBCLASSOF*0..]->(s:`Class`)<-[:DOMAIN]-(d:`DatatypeProperty`)
    RETURN DISTINCT d
    """
    query_object_forward = """
    MATCH (n {uri: $uri})-[:SUBCLASSOF*0..]->(s:`Class`)<-[:DOMAIN]-(d:`ObjectProperty`)-[:RANGE]->(r:`Class`)
    RETURN DISTINCT d, r
    """
    params_list: List[Dict[str, Any]] = []
    obj_params_list: List[Dict[str, Any]] = []
    with self._driver.session(**self._session_kwargs()) as session:
        for record in session.run(query_datatype, {"uri": class_uri}):
            d = record["d"]
            d_props = dict(d)
            params_list.append({"title": d_props.get("title", ""), "uri": d_props.get("uri", "")})
        for record in session.run(query_object_forward, {"uri": class_uri}):
            d = record["d"]
            r = record["r"]
            d_props = dict(d)
            r_props = dict(r)
            obj_params_list.append({
                "title": d_props.get("title", ""),
                "uri": d_props.get("uri", ""),
                "target_class_uri": r_props.get("uri", ""),
                "relation_direction": 1
            })
    return {"params": params_list, "obj_params": obj_params_list}
```

### Example usage

```python
with Neo4jRepository(config) as repo:
    signature = repo.collect_signature(class_uri)
    print("DatatypeProperty:", signature["params"])
    print("ObjectProperty:", signature["obj_params"])
```

Собирает сигнатуру класса - все `DatatypeProperty` и `ObjectProperty`, определённые для данного класса и его родителей (по иерархии `SUBCLASSOF*0..`).

Возвращает словарь:
```python
{
    "params": [
        {"title": "name", "uri": "http://ontology.com/xxx"},
        {"title": "age", "uri": "http://ontology.com/yyy"}
    ],
    "obj_params": [
        {"title": "teaches", "uri": "http://ontology.com/zzz", "target_class_uri": "http://ontology.com/aaa", "relation_direction": 1}
    ]
}
```

`relation_direction: 1` означает прямое отношение (от текущего объекта к другому).
