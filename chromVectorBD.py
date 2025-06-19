import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# 1. Загружаем модель для эмбеддингов
model = SentenceTransformer("all-MiniLM-L6-v2")

# 2. Инициализируем локальную базу
chroma_client = chromadb.PersistentClient(path="./chroma_db") 
#
chroma_client.delete_collection(name="products")

# 3. Создаём коллекцию (категорию товаров)
collection = chroma_client.get_or_create_collection(name="products")

# 4. Добавим товары
products = [
    "Кофемашина Bosch Tassimo Vivy. Давление: 3.3 бар. Цвет: чёрный.",
    "Кофемашина DeLonghi Magnifica. Давление: 15 бар. Автоматическая.",
    "Чайник Xiaomi Mi Kettle. Объём: 1.5 л. Мощность: 1800 Вт.",
]
embeddings = model.encode(products)

# Добавление в коллекцию
collection.add(
    documents=products,
    embeddings=embeddings.tolist(),
    ids=[f"product_{i}" for i in range(len(products))],
    metadatas=[{"название": p.split('.')[0]} for p in products]
)
print("База данных создана")
#=======================================================
# 5. Запрос от пользователя
# query = "автоматическая кофемашина высокого давления"
# query_vec = model.encode(query)

# # 6. Поиск
# results = collection.query(
#     query_embeddings=[query_vec],
#     n_results=2
# )

# print("\n🔍 Похожие товары:")
# for item in results["documents"][0]:
#     print("-", item)
