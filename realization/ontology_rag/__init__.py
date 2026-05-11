import os
import logging
import re
import warnings

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HUGGINGFACE_HUB_DISABLE_TELEMETRY"] = "1"
warnings.filterwarnings("ignore")

from typing import Dict, List, Optional

import numpy as np
from openai import OpenAI

from .ontology_loader import (
    load_ontology,
    build_uri_to_node,
    build_label_map,
    build_property_label_map,
    build_arc_index,
    build_node_descriptions,
)
from .constants import RDFS_LABEL
from .phase1_index import index, retrieve
from .phase2_retrieve import phase2_retrieve_and_generate
from .phase3_final import phase3_second_retrieval, phase3_final_generation
from .markup_loader import load_all_markups, build_entity_fragment_index, retrieve_text_fragments

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
logger = logging.getLogger("OntologyRAG")


class OntologyRAG:
    def __init__(
        self,
        ontology_path: str,
        model_name: str = "deepseek/deepseek-v4-flash",
        embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        llm_base_url: str = "https://polza.ai/api/v1",
        llm_api_key: str = None,
        cache_dir: str = None,
        markup_dir: str = None,
        fragment_K: int = 2,
        fragment_L: int = 3,
    ):
        self.ontology_path = ontology_path
        self.model_name = model_name
        self.embedding_model_name = embedding_model_name
        self.llm_base_url = llm_base_url
        self.fragment_K = fragment_K
        self.fragment_L = fragment_L

        if llm_api_key is None:
            llm_api_key = os.environ.get("POLZA_AI_API_KEY", "unused")
        self.llm_api_key = llm_api_key

        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(ontology_path), ".rag_cache")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        logger.info("Loading ontology from %s", ontology_path)
        self.ontology = load_ontology(ontology_path)
        self.uri_to_node = build_uri_to_node(self.ontology)
        self.uri_to_label = build_label_map(self.ontology)
        self.prop_uri_to_label = build_property_label_map(self.ontology, self.uri_to_label)
        self.arc_index = build_arc_index(self.ontology)

        logger.info("Building node descriptions...")
        all_descriptions = build_node_descriptions(
            self.ontology,
            self.uri_to_label,
            self.prop_uri_to_label,
            self.arc_index,
            self.uri_to_node,
        )

        from .constants import OWL_NAMED_INDIVIDUAL, W3_PREFIX
        self.node_descriptions = {}
        for uri, desc in all_descriptions.items():
            node = self.uri_to_node[uri]
            labels = node["data"].get("labels", [])
            if OWL_NAMED_INDIVIDUAL in labels:
                out_arcs = self.arc_index["outgoing"].get(uri, [])
                in_arcs = self.arc_index["incoming"].get(uri, [])
                has_obj_prop = any(
                    not a["arc_uri"].startswith(W3_PREFIX)
                    for a in out_arcs + in_arcs
                )
                pv = node["data"].get("params_values", {})
                has_datatype = any(
                    k not in (RDFS_LABEL, "uri")
                    for k in pv
                ) if "uri" in pv else any(
                    k != RDFS_LABEL for k in pv
                )
                if not has_obj_prop and not has_datatype:
                    continue
            self.node_descriptions[uri] = desc

        skipped = len(all_descriptions) - len(self.node_descriptions)
        if skipped:
            logger.info("Filtered out %d isolated nodes", skipped)

        self.embeddings: Optional[np.ndarray] = None
        self.client = OpenAI(base_url=self.llm_base_url, api_key=self.llm_api_key)

        self.uri_to_fragments: Dict[str, List[str]] = {}
        if markup_dir:
            logger.info("Loading markup files from %s", markup_dir)
            markups = load_all_markups(markup_dir)
            if markups:
                self.uri_to_fragments = build_entity_fragment_index(markups, K=fragment_K)
        elif os.path.isdir(os.path.join(os.path.dirname(ontology_path), 'markup')):
            markup_dir = os.path.join(os.path.dirname(ontology_path), 'markup')
            logger.info("Auto-detected markup dir: %s", markup_dir)
            markups = load_all_markups(markup_dir)
            if markups:
                self.uri_to_fragments = build_entity_fragment_index(markups, K=fragment_K)

        enriched_count = 0
        for uri, fragments in self.uri_to_fragments.items():
            if uri in self.node_descriptions and fragments:
                desc = self.node_descriptions[uri]
                desc_words = set(desc.lower().split())
                best_frag = None
                best_overlap = -1
                for frag in fragments:
                    frag_words = set(frag.lower().split())
                    overlap = len(desc_words & frag_words)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_frag = frag
                if best_frag is None:
                    best_frag = fragments[0]
                if len(best_frag) > 300:
                    best_frag = best_frag[:300] + "..."
                desc = re.sub(r'\nОписание: .+', '', desc)
                desc += f"\nОписание: {best_frag}"
                self.node_descriptions[uri] = desc
                enriched_count += 1
        if enriched_count:
            logger.info("Enriched %d node descriptions with text fragments", enriched_count)

        self.node_uris = list(self.node_descriptions.keys())
        self.node_texts = list(self.node_descriptions.values())

    def index(self, force_reindex: bool = False):
        self.embeddings = index(
            self.node_uris,
            self.node_texts,
            self.embedding_model_name,
            self.cache_dir,
            force_reindex=force_reindex,
        )

    def retrieve(self, query: str, top_n: int = 10):
        if self.embeddings is None:
            raise RuntimeError("Call index() before retrieve()")
        return retrieve(
            query,
            self.node_uris,
            self.node_texts,
            self.embeddings,
            self.embedding_model_name,
            top_n=top_n,
        )

    def answer(self, query: str, top_n: int = 10, top_m: int = 3) -> dict:
        if self.embeddings is None:
            raise RuntimeError("Call index() before answer()")

        p2 = phase2_retrieve_and_generate(
            query,
            self.node_uris,
            self.node_texts,
            self.embeddings,
            self.embedding_model_name,
            self.client,
            self.model_name,
            top_n=top_n,
        )

        if not p2["n_texts"]:
            return {
                "query": query,
                "initial_answer": p2["initial_answer"],
                "final_answer": p2["initial_answer"],
                "phase2_nodes": [
                    {"uri": uri, "text": text, "score": score}
                    for uri, text, score in p2["n_results"]
                ],
                "phase3_nodes": [],
            }

        p3 = phase3_second_retrieval(
            query,
            p2["initial_answer"],
            p2["n_uris"],
            self.node_uris,
            self.node_texts,
            self.embeddings,
            self.embedding_model_name,
            self.client,
            self.model_name,
            top_m=top_m,
        )

        p2_texts = p2["n_texts"]
        p3_texts = p3["m_texts"]

        all_entity_uris = list(p2["n_uris"] | p3["m_uris"])
        text_fragments = {}
        if self.uri_to_fragments and all_entity_uris:
            text_fragments = retrieve_text_fragments(
                all_entity_uris,
                self.uri_to_fragments,
                query,
                self.embedding_model_name,
                top_l=self.fragment_L,
            )
            logger.info("Retrieved text fragments for %d entities", len(text_fragments))

        final_answer = phase3_final_generation(
            query,
            p2_texts,
            p3_texts,
            self.client,
            self.model_name,
            text_fragments=text_fragments,
        )

        return {
            "query": query,
            "initial_answer": p2["initial_answer"],
            "final_answer": final_answer,
            "phase2_nodes": [
                {"uri": uri, "text": text, "score": score}
                for uri, text, score in p2["n_results"]
            ],
            "phase3_nodes": [
                {"uri": uri, "text": text, "score": score}
                for uri, text, score in p3["m_results"]
                if uri in p3["m_uris"]
            ],
            "text_fragments": text_fragments,
        }