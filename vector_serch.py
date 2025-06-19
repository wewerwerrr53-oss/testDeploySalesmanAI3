

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Модель эмбеддингов
model = SentenceTransformer("paraphrase-MiniLM-L3-v2")

# Подключение к ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="products")

def get_similar_products(user_query: str, top_k: int = 3) -> list[str]:
    query_vec = model.encode(user_query)
    results = collection.query(query_embeddings=[query_vec], n_results=top_k)
    return results["documents"][0] if results["documents"] else []
