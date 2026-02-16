import random
import string
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict

from neo4j import GraphDatabase


class TNode(TypedDict):
    uri: str
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