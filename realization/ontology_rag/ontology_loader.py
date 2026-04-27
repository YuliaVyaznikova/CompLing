import json
import re
import logging
from typing import Dict, List

from .constants import (
    RDF_TYPE, RDFS_SUBCLASS, RDFS_LABEL, RDFS_COMMENT,
    OWL_CLASS, OWL_NAMED_INDIVIDUAL, OWL_OBJECT_PROPERTY, OWL_DATATYPE_PROPERTY,
    W3_PREFIX,
)

logger = logging.getLogger("OntologyRAG")


def _split_camel_case(s: str) -> str:
    if not s or ' ' in s:
        return s
    result = re.sub(r'(?<=[а-яёa-z])(?=[А-ЯЁA-Z])', ' ', s)
    words = result.split()
    if len(words) <= 1:
        return s
    return words[0] + ' ' + ' '.join(w.lower() for w in words[1:])


def extract_ru_label(label_field) -> str:
    raw = ""
    if isinstance(label_field, list):
        for item in label_field:
            if isinstance(item, str) and item.endswith("@ru"):
                raw = item.replace("@ru", "")
                break
        if not raw:
            for item in label_field:
                if isinstance(item, str) and item.endswith("@en"):
                    raw = item.replace("@en", "")
                    break
        if not raw:
            raw = str(label_field[0]) if label_field else ""
    else:
        raw = str(label_field) if label_field else ""
    return _split_camel_case(raw)


def load_ontology(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_uri_to_node(ontology: dict) -> Dict[str, dict]:
    return {n["data"]["uri"]: n for n in ontology["nodes"]}


def build_label_map(ontology: dict) -> Dict[str, str]:
    label_map = {}
    for node in ontology["nodes"]:
        uri = node["data"]["uri"]
        label_field = node["data"].get(RDFS_LABEL, "")
        label = extract_ru_label(label_field)
        if not label:
            pv = node["data"].get("params_values", {})
            if RDFS_LABEL in pv:
                label = extract_ru_label(pv[RDFS_LABEL])
        label_map[uri] = label
    return label_map


def build_property_label_map(ontology: dict, uri_to_label: Dict[str, str]) -> Dict[str, str]:
    prop_map = {}
    for node in ontology["nodes"]:
        labels = node["data"].get("labels", [])
        if OWL_OBJECT_PROPERTY in labels or OWL_DATATYPE_PROPERTY in labels:
            uri = node["data"]["uri"]
            prop_map[uri] = uri_to_label.get(uri, uri.split("/")[-1])
    return prop_map


def get_node_type(node: dict) -> str:
    labels = node["data"].get("labels", [])
    if OWL_NAMED_INDIVIDUAL in labels:
        return "NamedIndividual"
    elif OWL_OBJECT_PROPERTY in labels:
        return "ObjectProperty"
    elif OWL_DATATYPE_PROPERTY in labels:
        return "DatatypeProperty"
    elif OWL_CLASS in labels:
        return "Class"
    return "Unknown"


def build_arc_index(ontology: dict) -> Dict[str, Dict[str, List[dict]]]:
    outgoing: Dict[str, List[dict]] = {}
    incoming: Dict[str, List[dict]] = {}
    for arc in ontology["arcs"]:
        src = arc["source"]
        tgt = arc["target"]
        arc_uri = arc["data"]["uri"]
        outgoing.setdefault(src, []).append({"arc_uri": arc_uri, "target": tgt})
        incoming.setdefault(tgt, []).append({"arc_uri": arc_uri, "source": src})
    return {"outgoing": outgoing, "incoming": incoming}


def _prettify_prop_label(s: str) -> str:
    if not s:
        return s
    s = s.replace("_", " ")
    return s[0].upper() + s[1:]


def _get_type_label(uri: str, uri_to_label: Dict[str, str], arc_index: Dict[str, Dict[str, List[dict]]]) -> str:
    for arc in arc_index["outgoing"].get(uri, []):
        if arc["arc_uri"] == RDF_TYPE:
            return uri_to_label.get(arc["target"], "")
    return ""


def node_to_text(
    node: dict,
    uri_to_label: Dict[str, str],
    prop_uri_to_label: Dict[str, str],
    arc_index: Dict[str, Dict[str, List[dict]]],
    uri_to_node: Dict[str, dict],
) -> str:
    uri = node["data"]["uri"]
    label = uri_to_label.get(uri, "")
    out_arcs = arc_index["outgoing"].get(uri, [])
    in_arcs = arc_index["incoming"].get(uri, [])
    lines = []

    lines.append(f"Название: {label}")

    for arc in out_arcs:
        if arc["arc_uri"] == RDF_TYPE:
            class_label = uri_to_label.get(arc["target"], "")
            if class_label:
                lines.append(f"Тип: {class_label}")

    for arc in out_arcs:
        if arc["arc_uri"] == RDFS_SUBCLASS:
            parent_label = uri_to_label.get(arc["target"], "")
            if parent_label:
                lines.append(f"Подкласс: {parent_label}")

    pv = node["data"].get("params_values", {})
    for param_uri, value in pv.items():
        if param_uri in (RDFS_LABEL, "uri"):
            continue
        prop_label = prop_uri_to_label.get(param_uri, param_uri.split("/")[-1])
        prop_label = _prettify_prop_label(prop_label)
        if isinstance(value, list):
            value = ", ".join(str(v).replace("@ru", "").replace("@en", "") for v in value)
        lines.append(f"{prop_label}: {value}")

    for arc in out_arcs:
        arc_uri = arc["arc_uri"]
        if arc_uri.startswith(W3_PREFIX):
            continue
        prop_label = _prettify_prop_label(prop_uri_to_label.get(arc_uri, arc_uri.split("/")[-1]))
        target_label = uri_to_label.get(arc["target"], "")
        if target_label:
            target_type = _get_type_label(arc["target"], uri_to_label, arc_index)
            if target_type:
                lines.append(f"{prop_label} {target_type}: {target_label}")
            else:
                lines.append(f"{prop_label}: {target_label}")

    for arc in in_arcs:
        arc_uri = arc["arc_uri"]
        if arc_uri.startswith(W3_PREFIX):
            continue
        prop_label = _prettify_prop_label(prop_uri_to_label.get(arc_uri, arc_uri.split("/")[-1]))
        source_label = uri_to_label.get(arc["source"], "")
        if source_label:
            source_type = _get_type_label(arc["source"], uri_to_label, arc_index)
            if source_type:
                lines.append(f"Входящая: {source_label} ({source_type}) {prop_label.lower()}")
            else:
                lines.append(f"Входящая: {source_label} {prop_label.lower()}")

    node_labels = node["data"].get("labels", [])
    if OWL_CLASS in node_labels:
        instances = []
        for arc in arc_index["incoming"].get(uri, []):
            if arc["arc_uri"] == RDF_TYPE:
                inst_label = uri_to_label.get(arc["source"], "")
                if inst_label:
                    instances.append(inst_label)
        if instances:
            instances.sort()
            if len(instances) > 7:
                lines.append(f"Экземпляры: {', '.join(instances[:7])} и другие")
            else:
                lines.append(f"Экземпляры: {', '.join(instances)}")

    comment = pv.get(RDFS_COMMENT, "")
    if comment:
        lines.append(f"Описание: {comment}")

    return "\n".join(lines)


def build_node_descriptions(
    ontology: dict,
    uri_to_label: Dict[str, str],
    prop_uri_to_label: Dict[str, str],
    arc_index: Dict[str, Dict[str, List[dict]]],
    uri_to_node: Dict[str, dict],
) -> Dict[str, str]:
    descriptions = {}
    for node in ontology["nodes"]:
        uri = node["data"]["uri"]
        desc = node_to_text(node, uri_to_label, prop_uri_to_label, arc_index, uri_to_node)
        descriptions[uri] = desc
    return descriptions