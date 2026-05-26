"""Quick end-to-end test of the RAG pipeline (embeddings + vector store + retrieval)."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Pull shared code from rag_chatbot without executing run()
src = open("rag_chatbot.py", encoding="utf-8").read()
exec(src.split("def run():")[0])  # noqa: S102

from openai import OpenAI
client_obj = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("=== Loading documents ===")
records = load_documents(Path("data"))
print(f"Total chunks: {len(records)}\n")

print("=== Building vector store ===")
collection = build_vector_store(records, client_obj)

print("\n=== Retrieval test ===")
questions = [
    "What is photosynthesis?",
    "How do you solve a linear equation?",
    "What are the parts of speech in English?",
    "Name the continents of the world",
]
for q in questions:
    chunks = retrieve_context(q, collection, client_obj)
    print(f"Q: {q}")
    for c in chunks:
        subj = c["subject"]
        sim  = c["similarity"]
        snip = c["text"][:70]
        print(f"  -> [{subj}] sim={sim:.4f}  {snip}...")
    print()

print("=== Full answer test ===")
answer, _ = ask("What is photosynthesis and why is it important?", collection, client_obj)
print(f"Answer: {answer}\n")

print("ALL TESTS PASSED")
