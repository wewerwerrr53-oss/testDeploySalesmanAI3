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
import logging
from flask_compress import Compress
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Загрузка переменных окружения
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Инициализация Flask
app = Flask(__name__)
Compress(app)

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

def qwen_request_with_timeout(messages, timeout_sec=35):
    """Безопасный вызов модели Qwen с ограничением по времени"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            lambda: client.chat.completions.create(model="qwen-plus", messages=messages)
        )
        try:
            return future.result(timeout=timeout_sec)
        except TimeoutError:
            raise Exception(f"⏰ Модель не ответила за {timeout_sec} секунд.")


@app.route("/chat", methods=["POST"])
def chat():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid token"}), 401

    try:
        user_id = verify_token(auth.split(" ")[1])
    except Exception as e:
        logging.warning(f"Invalid token: {e}")
        return jsonify({"error": "Invalid token"}), 401

    get_or_create_user(user_id)

    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Message is required"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    history = user_histories.get(user_id, [])
    messages = [{"role": "system", "content": build_system_prompt()}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = qwen_request_with_timeout(messages, timeout_sec=35)
        answer = completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Ошибка при обращении к модели: {e}")
        answer = "⏰ Модель не ответила вовремя. Попробуйте чуть позже."

    history.extend([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": answer}
    ])
    user_histories[user_id] = history[-10:]

    return jsonify({"reply": answer})



# @app.route("/stats", methods=["GET"])
# def stats():
#     """Публичная статистика — можно оставить без защиты"""
#     conn = sqlite3.connect("users.db")
#     cursor = conn.cursor()
#     cursor.execute("SELECT COUNT(*) FROM users")
#     total = cursor.fetchone()[0]
#     conn.close()
#     return jsonify({"total_users": total})


# @app.route("/test_timeout")
# def test_timeout():
#     import time
#     import logging

#     start = time.time()
#     try:
#         logging.info("🚀 Тест Qwen с timeout=1 начат")
#         completion = client.chat.completions.create(
#             model="qwen-plus",
#             messages=[{"role": "user", "content": "Привет, мир!"}],
#             timeout=1  # намеренно очень маленький timeout
#         )
#         answer = completion.choices[0].message.content
#         result = f"✅ Ответ получен: {answer[:100]}..."
#     except Exception as e:
#         result = f"⚠️ Ошибка: {type(e).__name__} — {e}"

#     duration = round(time.time() - start, 2)
#     return jsonify({"duration": duration, "result": result})



# =========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    # qwemChatWebDbTok
   # docker build -t hutarka .
#docker run -p 5000:5000 hutarka