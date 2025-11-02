from concurrent.futures import ThreadPoolExecutor, TimeoutError
from openai import OpenAI
import os

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
client = OpenAI(api_key=QWEN_API_KEY, base_url=BASE_URL)

def qwen_request_with_timeout(messages, timeout_sec=35):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            lambda: client.chat.completions.create(model="qwen-plus", messages=messages)
        )
        return future.result(timeout=timeout_sec)
