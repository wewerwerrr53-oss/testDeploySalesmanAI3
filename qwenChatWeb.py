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

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Получаем список разрешенных доменов из переменной окружения
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5000').split(',')

# Настройка CORS через переменные окружения
CORS(app, resources={r"/*": {
    "origins": ALLOWED_ORIGINS,
    "methods": ["GET", "POST"],
    "allow_headers": ["Content-Type"]
}})
user_histories = {}

# Настройки API Qwen
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

client = OpenAI(api_key=QWEN_API_KEY, base_url=BASE_URL)

def extract_vector_query(text: str) -> str | None:
    pattern = re.compile(r"\{\{VECTOR_QUERY:\s*((?:(?!\}\}).)*?)\s*\}\}", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else None

def build_system_prompt():
    return """
Ты — дружелюбный помощник программиста, который размещён на его сайте. Твоя задача — рассказать о разработчике и его услугах, а также помочь оставить заявку на сотрудничество.
Взаимодействуй с пользователем в естественном диалоге, дружелюбно, но профессионально.

Если пользователь заинтересован — кратко и понятно расскажи о разработчике:
•	Java-разработчик с опытом создания веб-приложений, чат-ботов с ИИ, интернет-магазинов.
•	Владение Java, Spring Boot, Hibernate, React, MySQL, Docker.
•	Создаёт REST API, CRM-системы, чат-ботов с LLM и векторными БД (chromadb, sentence-transformers), делает интеграции и деплой.
•	Умеет работать с заказчиком, собирать требования и поддерживать проект.
После интереса к сотрудничеству предложи оформить заявку.

Собирай данные поочерёдно по одному пункту, в такой последовательности:
1.	Имя
2.	Контакт (email, Telegram или другое)
3.	Что нужно сделать (суть задачи)
После сбора всех данных выведи информацию в следующем формате:
[ORDER_START]  
Имя: {name}  
Контакт: {contact}  
Запрос: {request}  
[ORDER_END]

Если пользователь не указал какой-либо пункт — не добавляй его в заказ.
Сохраняй последовательность, вежливость и простоту общения.
"""

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id", "default_user")
    user_message = data.get("message")

    history = user_histories.get(user_id, [])
    messages = [{"role": "system", "content": build_system_prompt()}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = client.chat.completions.create(model="qwen-plus", messages=messages)
        answer = completion.choices[0].message.content

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
        order_data = parse_order(answer)
        if order_data:
            success = send_order_to_email(order_data)
            if success:
                answer += "\n\n✅ Заказ успешно отправлен!"
            else:
                answer += "\n\n❌ Ошибка при отправке заказа."

        return jsonify({"reply": answer})

    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        return jsonify({"reply": f"Произошла ошибка: {str(e)}"}), 500

if __name__ == "__main__":
    # Получаем порт из переменных окружения (Railway автоматически устанавливает PORT)
    port = int(os.getenv("PORT", 5000))
    # Запускаем в production режиме
    app.run(host='0.0.0.0', port=port)





#docker build -t salor-ai .
#docker run --rm --env-file .env chroma-app
#docker run --rm --env-file .env -p 5000:5000 salor-ai