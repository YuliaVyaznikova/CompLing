import os
import sys
from datetime import datetime
import traceback

from func import Neo4jConfig, Neo4jRepository


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()


log_path = os.path.join(os.path.dirname(__file__), "usage_log.txt")
with open(log_path, "w", encoding="utf-8") as log_file:
    _orig_out = sys.stdout
    _orig_err = sys.stderr
    try:
        sys.stdout = _Tee(sys.__stdout__, log_file)
        sys.stderr = _Tee(sys.__stderr__, log_file)

        started_at = datetime.now().isoformat(timespec="seconds")
        print(f"Started at: {started_at}")

        config = Neo4jConfig(
            uri="bolt://127.0.0.1:7687",
            user="neo4j",
            password="vud_898_8",
            database=None,
        )

        print(f"Connection URI: {config.uri}")
        print(f"User: {config.user}")
        print(f"Database: {config.database}")

        with Neo4jRepository(config) as repo:
            print("\n=== Task #1: Node and Arc Operations===\n")

            created_1 = repo.create_node({"label": "Entity", "description": "test"})
            print("Created node 1:", created_1)

            created_2 = repo.create_node({"label": "Entity", "description": "test2"})
            print("Created node 2:", created_2)

            node = repo.get_node_by_uri(created_1["uri"])
            print("Fetched node:", node)

            updated = repo.update_node(created_1["uri"], {"description": "updated"})
            print("Updated node:", updated)

            nodes = repo.get_nodes_by_labels(["Entity"])
            print("Nodes by label:", nodes)

            all_nodes, all_arcs = repo.get_all_nodes_and_arcs()
            print("All nodes:", all_nodes)
            print("All arcs:", all_arcs)

            arc = repo.create_arc(created_1["uri"], created_2["uri"], rel_type="RELATED")
            print("Created arc:", arc)

            all_nodes_after, all_arcs_after = repo.get_all_nodes_and_arcs()
            print("All nodes after arc:", all_nodes_after)
            print("All arcs after arc:", all_arcs_after)

            arc_deleted = repo.delete_arc_by_id(arc["id"])
            print("Deleted arc:", arc_deleted)

            deleted_1 = repo.delete_node_by_uri(created_1["uri"])
            print("Deleted node 1:", deleted_1)

            deleted_2 = repo.delete_node_by_uri(created_2["uri"])
            print("Deleted node 2:", deleted_2)

            print("\n=== Task #2: Ontology methods ===\n")

            parent_class = repo.create_class("Person", "A human being")
            print("Created parent class:", parent_class)

            child_class = repo.create_class("Student", "A person who studies", parent_uri=parent_class["uri"])
            print("Created child class:", child_class)

            child_class2 = repo.create_class("Teacher", "A person who teaches", parent_uri=parent_class["uri"])
            print("Created child class 2:", child_class2)

            parent_classes = repo.get_ontology_parent_classes()
            print("Ontology parent classes:", parent_classes)

            fetched_class = repo.get_class(parent_class["uri"])
            print("Fetched class:", fetched_class)

            parents = repo.get_class_parents(child_class["uri"])
            print("Class parents:", parents)

            children = repo.get_class_children(parent_class["uri"])
            print("Class children:", children)

            updated_class = repo.update_class(parent_class["uri"], title="Human", description="Updated description")
            print("Updated class:", updated_class)

            attr_name = repo.add_class_attribute(parent_class["uri"], "name")
            print("Added DatatypeProperty:", attr_name)

            attr_age = repo.add_class_attribute(parent_class["uri"], "age")
            print("Added DatatypeProperty:", attr_age)

            obj_attr = repo.add_class_object_attribute(parent_class["uri"], "teaches", child_class["uri"])
            print("Added ObjectProperty:", obj_attr)

            signature = repo.collect_signature(parent_class["uri"])
            print("Signature:", signature)

            obj = repo.create_object(parent_class["uri"], "John Doe", "A test person", properties={attr_name["uri"]: "John", attr_age["uri"]: 25})
            print("Created object:", obj)

            fetched_obj = repo.get_object(obj["uri"])
            print("Fetched object:", fetched_obj)

            class_objects = repo.get_class_objects(parent_class["uri"])
            print("Class objects:", class_objects)

            updated_obj = repo.update_object(obj["uri"], title="John Smith", properties={attr_name["uri"]: "John S."})
            print("Updated object:", updated_obj)

            all_nodes_onto, all_arcs_onto = repo.get_ontology()
            print("Ontology nodes:", len(all_nodes_onto))
            print("Ontology arcs:", len(all_arcs_onto))

            deleted_obj = repo.delete_object(obj["uri"])
            print("Deleted object:", deleted_obj)

            deleted_attr = repo.delete_class_attribute(attr_name["uri"])
            print("Deleted DatatypeProperty:", deleted_attr)

            deleted_obj_attr = repo.delete_class_object_attribute(obj_attr["uri"])
            print("Deleted ObjectProperty:", deleted_obj_attr)

            deleted_class = repo.delete_class(parent_class["uri"])
            print("Deleted class (cascade):", deleted_class)

        finished_at = datetime.now().isoformat(timespec="seconds")
        print(f"Finished at: {finished_at}")
        print(f"Log saved to: {log_path}")
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout = _orig_out
        sys.stderr = _orig_err