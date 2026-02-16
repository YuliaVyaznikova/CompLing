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

        finished_at = datetime.now().isoformat(timespec="seconds")
        print(f"Finished at: {finished_at}")
        print(f"Log saved to: {log_path}")
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout = _orig_out
        sys.stderr = _orig_err