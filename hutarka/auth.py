from flask import Blueprint, request, jsonify
import uuid, jwt, datetime, os
from .database import add_user_if_not_exists
from .limiter import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-prod")

def issue_token(user_id):
    payload = {"user_id": user_id, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token, allow_expired=False):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        if allow_expired:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
            return payload["user_id"]
        raise

@auth_bp.route("/init", methods=["POST"])
@limiter.limit("5 per minute")
def init_auth():
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
        try:
            user_id = verify_token(token)
            return jsonify({"token": token, "user_id": user_id})
        except jwt.ExpiredSignatureError:
            user_id = verify_token(token, allow_expired=True)
            new_token = issue_token(user_id)
            return jsonify({"token": new_token, "user_id": user_id})
        except Exception:
            pass

    user_id = str(uuid.uuid4())
    add_user_if_not_exists(user_id)
    token = issue_token(user_id)
    return jsonify({"token": token, "user_id": user_id})
