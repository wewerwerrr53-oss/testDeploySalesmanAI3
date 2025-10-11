import os
import re
import logging
import jwt
import datetime
import uuid
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI
from qwenGmail import send_order_to_email
from qwenparser import parse_order
from vector_serch import get_similar_products
import sqlite3

# Загрузка переменных окружения
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Инициализация Flask
app = Flask(__name__)

# Секретный ключ для JWT (обязательно задай в .env!)
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")

# =========================================
# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()
# =========================================

# CORS
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, resources={r"/*": {
    "origins": ALLOWED_ORIGINS,
    "methods": ["GET", "POST"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

# Хранение истории чатов в памяти (временно)
user_histories = {}

# Настройки Qwen API
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
client = OpenAI(api_key=QWEN_API_KEY, base_url=BASE_URL)

# =========================================
# Вспомогательные функции
def get_or_create_user(user_id: str):
    """Создаёт пользователя, если его нет"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    return user_id

def issue_token(user_id: str) -> str:
    """Генерирует JWT-токен на 30 дней"""
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str, allow_expired: bool = False) -> str:
    """Проверяет токен и возвращает user_id"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        if allow_expired:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
            return payload["user_id"]
        else:
            raise Exception("Token expired")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token")

def extract_vector_query(text: str) -> str | None:
    pattern = re.compile(r"\{\{VECTOR_QUERY:\s*((?:(?!\}\}).)*?)\s*\}\}", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None

def build_system_prompt():
    return """
Общайся только на РУССКОМ
Ты — Hutarka, первый искусственный интеллект созданный в Беларуси, в Беларуси все говорят по русски.  
Если запрос не содержит уточнения, по умолчанию ВСЕ твои ответы должны быть на русском языке.  

Стиль общения:
-Русский язык — основа.  
- Будь простым и живым: отвечай так, чтобы с тобой было интересно разговаривать. 
- Добавляй лёгкий юмор, иногда шуткуй по-белорусски, но не перегибай. 
- Если пользователь попросит, можешь полностью перейти на белорусский язык. 

Особенности:
- Если уместно, используй культурные или исторические ссылки на Беларусь (традиции, кухня, литература, быт). 
- Подстраивайся под стиль собеседника: можешь быть серьёзным экспертом или весёлым другом. 
- Избегай политики, агрессии и токсичности — Hutarka всегда уважителен. 

Главная цель — быть не бездушным ассистентом, а «собеседником с душой», с которым приятно поболтать, посмеяться и к которому хочется возвращаться. 
"""
# =========================================

# Эндпоинты

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/auth/init", methods=["POST"])
def auth_init():
    """Инициализация аутентификации: выдача или обновление токена"""
    auth = request.headers.get("Authorization")
    
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
        try:
            # Токен валиден?
            user_id = verify_token(token)
            return jsonify({"token": token, "user_id": user_id})
        except Exception:
            try:
                # Токен просрочен, но подлинный?
                user_id = verify_token(token, allow_expired=True)
                new_token = issue_token(user_id)
                return jsonify({"token": new_token, "user_id": user_id})
            except Exception:
                pass  # Игнорируем невалидный токен

    # Новый пользователь
    user_id = str(uuid.uuid4())
    get_or_create_user(user_id)
    token = issue_token(user_id)
    return jsonify({"token": token, "user_id": user_id})

@app.route("/chat", methods=["POST"])
def chat():
    """Основной эндпоинт чата — БЕЗ user_id в теле!"""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid token"}), 401

    try:
        user_id = verify_token(auth.split(" ")[1])  # Только валидные токены!
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    get_or_create_user(user_id)

    data = request.get_json()
    user_message = data.get("message")
    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    history = user_histories.get(user_id, [])
    messages = [{"role": "system", "content": build_system_prompt()}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = client.chat.completions.create(model="qwen-plus", messages=messages)
        answer = completion.choices[0].message.content

        # (Опционально) Векторный поиск — раскомментируй, если нужен
        # vector_query = extract_vector_query(answer)
        # if vector_query:
        #     similar_products = get_similar_products(vector_query)
        #     vector_text = "\n".join(similar_products) or "(ничего не найдено)"
        #     clean_answer = re.sub(r"\{\{VECTOR_QUERY:.*?\}\}", "", answer)
        #     messages = [{"role": "system", "content": build_system_prompt()}] + history + [
        #         {"role": "user", "content": user_message},
        #         {"role": "assistant", "content": clean_answer},
        #         {"role": "user", "content": f"Вот информация из базы:\n{vector_text}\n\n{user_message}"}
        #     ]
        #     completion = client.chat.completions.create(model="qwen-plus", messages=messages)
        #     answer = completion.choices[0].message.content

        # Обновляем историю
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": answer})
        if len(history) > 10:
            history = history[-10:]
        user_histories[user_id] = history

        # (Опционально) Обработка заказов
        # order_data = parse_order(answer)
        # if order_data:
        #     success = send_order_to_email(order_data)
        #     if success:
        #         answer += "\n\n✅ Заказ успешно отправлен!"
        #     else:
        #         answer += "\n\n❌ Ошибка при отправке заказа."

        return jsonify({"reply": answer})

    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        return jsonify({"reply": f"Произошла ошибка: {str(e)}"}), 500

@app.route("/stats", methods=["GET"])
def stats():
    """Публичная статистика — можно оставить без защиты"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    conn.close()
    return jsonify({"total_users": total})

# =========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    # qwemChatWebDbTok