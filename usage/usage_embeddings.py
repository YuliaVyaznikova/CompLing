import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "realization"))

from embeddings import get_chunks, get_embeddings, cos_compare, find_similar_chunks
from utils import LogContext


log_path = os.path.join(os.path.dirname(__file__), "usage_embeddings_log.txt")
with LogContext(log_path):
    try:
        started_at = datetime.now().isoformat(timespec="seconds")
        print(f"Started at: {started_at}")

        print("\n=== Task #3: Embeddings ===\n")

        sample_text = """
Тхэквондо ITF (International Taekwon-Do Federation) — это корейское боевое искусство, разработанное генералом Чой Хон Хи в 1955 году. Название происходит от корейских слов: "тхэ" — нога, "квон" — кулак, "до" — путь. Таким образом, тхэквондо переводится как "путь ноги и кулака".

В тхэквондо ITF изучается 24 туля (формальных комплексов упражнений). Каждый туль назван в честь исторической личности или события корейской истории. Тули выполняются в определённой последовательности и содержат от 19 до 72 движений.

Туль Чонджи — первый туль для начинающих, содержит 19 движений. Назван в честь легендарного озера Чонджи на вершине горы Пэктусан. Согласно легенде, это место рождения корейского народа.

Туль Дангун назван в честь легендарного основателя Кореи — Дангуна, который согласно мифу основал первое корейское государство в 2333 году до н.э. Этот туль содержит 21 движение.

Техника тхэквондо включает удары ногами, руками, блоки и стойки. Удары ногами составляют около 70% техники. Основные удары ногами: ап чаги (прямой удар), долльо чаги (круговой удар), йоп чаги (боковой удар), миро чаги (толкающий удар).

Спарринг в тхэквондо называется массоги. Существует несколько видов спарринга: базовый спарринг (три шага), полу-свободный спарринг и свободный спарринг. В соревнованиях используется спортивный спарринг с защитным снаряжением.

Система поясов в тхэквондо ITF включает 10 цветных поясов (гуп) от белого до красного с чёрной полосой, затем 9 данов чёрного пояса. Каждый уровень требует знания определённых тулей, техники и теории.

Философия тхэквондо основана на пяти принципах: учтивость, честность, настойчивость, самообладание и непоколебимость духа. Эти принципы являются основой тренировок.
"""

        print("=== 1. get_chunks ===\n")
        
        chunks_paragraph = get_chunks(sample_text, chunk_size=512, split_by="paragraph")
        print(f"Разбиение по абзацам ({len(chunks_paragraph)} фрагментов):")
        for i, chunk in enumerate(chunks_paragraph):
            print(f"  [{i}]: {chunk[:100]}..." if len(chunk) > 100 else f"  [{i}]: {chunk}")

        chunks_sentence = get_chunks(sample_text, chunk_size=200, split_by="sentence")
        print(f"\nРазбиение по предложениям ({len(chunks_sentence)} фрагментов):")
        for i, chunk in enumerate(chunks_sentence[:5]):
            print(f"  [{i}]: {chunk[:80]}..." if len(chunk) > 80 else f"  [{i}]: {chunk}")
        if len(chunks_sentence) > 5:
            print(f"  ... и ещё {len(chunks_sentence) - 5} фрагментов")

        print("\n=== 2. get_embeddings ===\n")
        
        print("Генерация эмбеддингов для фрагментов (по абзацам)...")
        embeddings = get_embeddings(chunks_paragraph)
        print(f"Размерность эмбеддингов: {embeddings.shape}")
        print(f"Тип данных: {embeddings.dtype}")

        single_embedding = get_embeddings("Тхэквондо — боевое искусство")
        print(f"Размерность одного эмбеддинга: {single_embedding.shape}")

        print("\n=== 3. cos_compare ===\n")

        text1 = "Тхэквондо изучает удары ногами"
        text2 = "В тхэквондо есть удары ногами"
        text3 = "Погода сегодня хорошая"

        emb1 = get_embeddings(text1)
        emb2 = get_embeddings(text2)
        emb3 = get_embeddings(text3)

        sim_12 = cos_compare(emb1[0], emb2[0])
        sim_13 = cos_compare(emb1[0], emb3[0])
        sim_23 = cos_compare(emb2[0], emb3[0])

        print(f"Сравнение похожих текстов:")
        print(f"  '{text1}'")
        print(f"  '{text2}'")
        print(f"  Сходство: {sim_12:.4f}")

        print(f"\nСравнение разных текстов:")
        print(f"  '{text1}'")
        print(f"  '{text3}'")
        print(f"  Сходство: {sim_13:.4f}")

        print(f"\nСходство текстов:")
        print(f"         text1   text2   text3")
        print(f"  text1  1.0000  {sim_12:.4f}  {sim_13:.4f}")
        print(f"  text2  {sim_12:.4f}  1.0000  {sim_23:.4f}")
        print(f"  text3  {sim_13:.4f}  {sim_23:.4f}  1.0000")

        print("\n=== 4. find_similar_chunks ===\n")

        queries = [
            "Какие тули изучаются в тхэквондо?",
            "Удары ногами в тхэквондо ITF",
            "Система поясов и данов",
            "Кто основал тхэквондо?"
        ]

        for query in queries:
            print(f"\nЗапрос: '{query}'")
            results = find_similar_chunks(query, chunks_paragraph, top_k=3)
            for r in results:
                print(f"  [{r['index']}] (sim={r['similarity']:.4f}): {r['chunk'][:80]}...")

        finished_at = datetime.now().isoformat(timespec="seconds")
        print(f"\nFinished at: {finished_at}")
        print(f"Log saved to: {log_path}")

    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()