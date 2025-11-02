import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY")
    RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
