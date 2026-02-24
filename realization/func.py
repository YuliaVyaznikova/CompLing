import random
import string
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict

from neo4j import GraphDatabase


class TNode(TypedDict):
    uri: str
    title: str
    description: str
    label: str


class TArc(TypedDict):
    id: str
    uri: str
    node_uri_from: str
    node_uri_to: str


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: Optional[str] = None


class Neo4jRepository:
    def __init__(self, config: Neo4jConfig):
        self._config = config
        self._driver = GraphDatabase.driver(config.uri, auth=(config.user, config.password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jRepository":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _session_kwargs(self) -> Dict[str, Any]:
        if self._config.database:
            return {"database": self._config.database}
        return {}

    def generate_random_string(self, length: int = 12, namespace_title: str = "ontology") -> str:
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(random.choice(alphabet) for _ in range(length))
        return f"http://{namespace_title}.com/{random_part}"

    def transform_labels(self, labels: Sequence[str], separator: str = ":") -> str:
        if not labels:
            return "``"
        return separator.join(f"`{l}`" for l in labels)

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

    def collect_node(self, node: Any) -> TNode:
        labels = list(getattr(node, "labels", []))
        props = dict(getattr(node, "_properties", {}))
        return {
            "uri": str(props.get("uri", "")),
            "title": str(props.get("title", "")),
            "description": str(props.get("description", "")),
            "label": str(labels[0]) if labels else "",
        }

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

    def run_custom_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self._driver.session(**self._session_kwargs()) as session:
            result = session.run(query, params or {})
            return [dict(r) for r in result]

    def get_all_nodes_and_arcs(self) -> Tuple[List[TNode], List[TArc]]:
        cypher = "MATCH (n) RETURN n AS node UNION ALL MATCH ()-[r]-() RETURN r AS node"

        nodes_by_uri: Dict[str, TNode] = {}
        arcs_by_id: Dict[str, TArc] = {}

        with self._driver.session(**self._session_kwargs()) as session:
            for record in session.run(cypher):
                item = record.get("node")
                if item is None:
                    continue
                if hasattr(item, "labels"):
                    node_dict = self.collect_node(item)
                    if node_dict["uri"]:
                        nodes_by_uri[node_dict["uri"]] = node_dict
                else:
                    arc_dict = self.collect_arc(item)
                    if arc_dict["id"]:
                        arcs_by_id[arc_dict["id"]] = arc_dict

        return list(nodes_by_uri.values()), list(arcs_by_id.values())

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

    def create_node(self, params: Dict[str, Any]) -> TNode:
        label = str(params.get("label", ""))
        if not label:
            raise ValueError("label is required")

        uri = str(params.get("uri") or self.generate_random_string())
        props: Dict[str, Any] = {"uri": uri}

        if "description" in params:
            props["description"] = params.get("description")

        if "title" in params:
            props["title"] = params.get("title")

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

    def delete_node_by_uri(self, uri: str) -> bool:
        cypher = "MATCH (n {uri: $uri}) DETACH DELETE n RETURN count(n) AS deleted"
        with self._driver.session(**self._session_kwargs()) as session:
            record = session.run(cypher, {"uri": uri}).single()
            if not record:
                return False
            return int(record.get("deleted", 0)) > 0

    def delete_arc_by_id(self, arc_id: str) -> bool:
        cypher = "MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r RETURN count(r) AS deleted"
        with self._driver.session(**self._session_kwargs()) as session:
            record = session.run(cypher, {"id": str(arc_id)}).single()
            if not record:
                return False
            return int(record.get("deleted", 0)) > 0

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

    def get_ontology(self) -> Tuple[List[TNode], List[TArc]]:
        return self.get_all_nodes_and_arcs()

    def get_ontology_parent_classes(self) -> List[TNode]:
        cypher = "MATCH (c:`Class`) WHERE NOT (c)-[:SUBCLASSOF]->() RETURN c AS node"
        with self._driver.session(**self._session_kwargs()) as session:
            return [self.collect_node(record.get("node")) for record in session.run(cypher)]

    def get_class(self, uri: str) -> Optional[TNode]:
        node = self.get_node_by_uri(uri)
        if node and node["label"] == "Class":
            return node
        return None

    def get_class_parents(self, uri: str) -> List[TNode]:
        cypher = "MATCH (c {uri: $uri})-[:SUBCLASSOF]->(p:`Class`) RETURN p AS node"
        with self._driver.session(**self._session_kwargs()) as session:
            return [self.collect_node(record.get("node")) for record in session.run(cypher, {"uri": uri})]

    def get_class_children(self, uri: str) -> List[TNode]:
        cypher = "MATCH (child:`Class`)-[:SUBCLASSOF]->(c {uri: $uri}) RETURN child AS node"
        with self._driver.session(**self._session_kwargs()) as session:
            return [self.collect_node(record.get("node")) for record in session.run(cypher, {"uri": uri})]

    def get_class_objects(self, class_uri: str) -> List[TNode]:
        cypher = "MATCH (o:`Object`)-[:INSTANCEOF]->(c {uri: $class_uri}) RETURN o AS node"
        with self._driver.session(**self._session_kwargs()) as session:
            return [self.collect_node(record.get("node")) for record in session.run(cypher, {"class_uri": class_uri})]

    def update_class(self, uri: str, title: Optional[str] = None, description: Optional[str] = None) -> Optional[TNode]:
        params = {}
        if title is not None:
            params["title"] = title
        if description is not None:
            params["description"] = description
        return self.update_node(uri, params)

    def create_class(self, title: str, description: str = "", parent_uri: Optional[str] = None) -> TNode:
        uri = self.generate_random_string()
        params = {"label": "Class", "uri": uri, "title": title, "description": description}
        node = self.create_node(params)
        if parent_uri:
            self.create_arc(node["uri"], parent_uri, "SUBCLASSOF")
        return node

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

    def add_class_attribute(self, class_uri: str, title: str) -> TNode:
        if not self.get_node_by_uri(class_uri):
            raise ValueError("Class not found")
        prop_uri = self.generate_random_string()
        prop = self.create_node({"label": "DatatypeProperty", "uri": prop_uri, "title": title})
        self.create_arc(prop["uri"], class_uri, "DOMAIN")
        return prop

    def delete_class_attribute(self, prop_uri: str) -> bool:
        node = self.get_node_by_uri(prop_uri)
        if not node or node["label"] != "DatatypeProperty":
            return False
        return self.delete_node_by_uri(prop_uri)

    def add_class_object_attribute(self, class_uri: str, attr_name: str, range_class_uri: str) -> TNode:
        if not self.get_node_by_uri(class_uri) or not self.get_node_by_uri(range_class_uri):
            raise ValueError("Class not found")
        prop_uri = self.generate_random_string()
        prop = self.create_node({"label": "ObjectProperty", "uri": prop_uri, "title": attr_name})
        self.create_arc(prop["uri"], class_uri, "DOMAIN")
        self.create_arc(prop["uri"], range_class_uri, "RANGE")
        return prop

    def delete_class_object_attribute(self, object_property_uri: str) -> bool:
        node = self.get_node_by_uri(object_property_uri)
        if not node or node["label"] != "ObjectProperty":
            return False
        return self.delete_node_by_uri(object_property_uri)

    def add_class_parent(self, parent_uri: str, target_uri: str):
        if not self.get_node_by_uri(parent_uri) or not self.get_node_by_uri(target_uri):
            raise ValueError("Class not found")
        self.create_arc(target_uri, parent_uri, "SUBCLASSOF")

    def get_object(self, uri: str) -> Optional[TNode]:
        node = self.get_node_by_uri(uri)
        if node and node["label"] == "Object":
            return node
        return None

    def delete_object(self, uri: str) -> bool:
        if not self.get_object(uri):
            return False
        return self.delete_node_by_uri(uri)

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