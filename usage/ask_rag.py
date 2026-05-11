import sys
import os
import logging

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realization.ontology_rag import OntologyRAG

for h in logging.getLogger().handlers[:]:
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
        logging.getLogger().removeHandler(h)


def main():
    print("start")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rag = OntologyRAG(
        ontology_path=os.path.join(base_dir, "ontology_all_films.json"),
        llm_api_key=os.environ.get("POLZA_AI_API_KEY"),
        markup_dir=os.path.join(base_dir, "markup"),
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