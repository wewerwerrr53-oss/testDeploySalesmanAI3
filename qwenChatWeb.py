import os
import re
import logging
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from openai import OpenAI
from qwenGmail import send_order_to_email
from qwenparser import parse_order
from vector_serch import get_similar_products
import sqlite3

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

#=========================================

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()

# создаём таблицу при старте сервера
init_db()
#========================================



# Получаем список разрешенных доменов из переменной окружения
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')

# Настройка CORS через переменные окружения
CORS(app, resources={r"/*": {
    "origins": ALLOWED_ORIGINS,
    "methods": ["GET", "POST"],
    "allow_headers": ["Content-Type"]
}})

#CORS(app, supports_credentials=True)


user_histories = {}

# Настройки API Qwen
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

client = OpenAI(api_key=QWEN_API_KEY, base_url=BASE_URL)

def extract_vector_query(text: str) -> str | None:
    pattern = re.compile(r"\{\{VECTOR_QUERY:\s*((?:(?!\}\}).)*?)\s*\}\}", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None


#====================================================
def add_user(user_id: str):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def count_users() -> int:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    result = cursor.fetchone()[0]
    conn.close()
    return result
#==================================





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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id", "default_user")
    user_message = data.get("message")



#======================
    add_user(user_id)
#========================



    history = user_histories.get(user_id, [])
    messages = [{"role": "system", "content": build_system_prompt()}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = qwen_request_with_timeout(messages, timeout_sec=25)
        answer = completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Ошибка при обращении к модели: {e}")
        answer = "⏰ Модель не ответила вовремя. Попробуйте чуть позже."

        # vector_query = extract_vector_query(answer)
        # if vector_query:
        #     similar_products = get_similar_products(vector_query)
        #     vector_text = "\n".join(similar_products) or "(ничего не найдено)"
        #     clean_answer = re.sub(r"\{\{VECTOR_QUERY:.*?\}\}", "", answer)

        #     messages.append({"role": "assistant", "content": clean_answer})
        #     messages.append({
        #         "role": "user",
        #         "content": f"Вот информация из базы:\n{vector_text}\n\n{user_message}"
        #     })

        #     completion = client.chat.completions.create(model="qwen-plus", messages=messages)
        #     answer = completion.choices[0].message.content

        # Обновляем историю
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": answer})
        if len(history) > 10:
            history = history[-10:]

        user_histories[user_id] = history

        # Проверка на заказ
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




#============================================
@app.route("/stats", methods=["GET"])
def stats():
    return jsonify({"total_users": count_users()})
#======================================       





if __name__ == "__main__":
    # Получаем порт из переменных окружения (Railway автоматически устанавливает PORT)
    port = int(os.getenv("PORT", 5000))
    # Запускаем в production режиме
    app.run(host='0.0.0.0', port=port)





#docker build -t salor-ai .
#docker run --rm --env-file .env chroma-app
#docker run --rm --env-file .env -p 5000:5000 salor-ai