from flask import Blueprint, request, jsonify
import logging
from .auth import verify_token
from .utils.recaptcha import verify_recaptcha
from .utils.qwen_client import qwen_request_with_timeout
from .database import add_user_if_not_exists
from .limiter import limiter

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

user_histories = {}

def build_system_prompt():
    return """
Ты — Hutarka, искусственный интеллект из Беларуси 🇧🇾.
Всегда отвечай на русском языке, будь дружелюбным и с чувством юмора.
"""

@chat_bp.route("", methods=["POST"])
@limiter.limit("10 per minute")
def chat():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Проверка reCAPTCHA
    ok, msg = verify_recaptcha(data.get("recaptcha_token"))
    if not ok:
        return jsonify({"error": msg}), 400

    # Проверка JWT
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401

    try:
        user_id = verify_token(auth.split(" ")[1])
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    add_user_if_not_exists(user_id)

    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    history = user_histories.get(user_id, [])
    messages = [{"role": "system", "content": build_system_prompt()}] + history + [
        {"role": "user", "content": user_message}
    ]

    try:
        completion = qwen_request_with_timeout(messages)
        answer = completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Qwen error: {e}")
        answer = "⚠️ Ошибка при обращении к модели."

    history.extend([{"role": "user", "content": user_message},
                    {"role": "assistant", "content": answer}])
    user_histories[user_id] = history[-10:]

    return jsonify({"reply": answer})
