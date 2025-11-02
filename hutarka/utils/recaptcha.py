import requests
import os
import logging

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

def verify_recaptcha(token: str) -> tuple[bool, str]:
    """Проверяет Google reCAPTCHA."""
    try:
        res = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": RECAPTCHA_SECRET_KEY, "response": token},
            timeout=5
        ).json()
        if not res.get("success"):
            logging.warning(f"reCAPTCHA failed: {res.get('error-codes', [])}")
            return False, "reCAPTCHA verification failed"
        if res.get("score", 1.0) < 0.5:
            return False, "Low reCAPTCHA score"
        return True, ""
    except Exception as e:
        logging.error(f"reCAPTCHA error: {e}")
        return False, "reCAPTCHA service unavailable"
