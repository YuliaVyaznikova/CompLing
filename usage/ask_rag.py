import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realization.ontology_rag import OntologyRAG

for h in logging.getLogger().handlers[:]:
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
        logging.getLogger().removeHandler(h)


def main():
    print("start")
    rag = OntologyRAG(
        ontology_path="C:/IMPORTANT/NSU/3/CL/6/ontology_all_films.json",
        model_name="qwen2.5:3b",
    )
    rag.index()
    print("ask smth or press ctrl+c for exit\n")

    while True:
        try:
            query = input("type here: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nend of work")
            break

        if not query:
            break

        result = rag.answer(query, top_n=10, top_m=3)
        print(f"\nanswer: {result['final_answer']}\n")


if __name__ == "__main__":
    main()