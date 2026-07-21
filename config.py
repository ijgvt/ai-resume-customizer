"""统一配置入口"""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
PROFILE_PATH = DATA_DIR / "profile.json"
OUTPUT_DIR = DATA_DIR / "outputs"
UPLOADS_DIR = DATA_DIR / "uploads"
RESUME_FILES_DIR = DATA_DIR / "resume_files"
PHOTOS_DIR = DATA_DIR / "photos"

for d in [DATA_DIR, OUTPUT_DIR, UPLOADS_DIR, RESUME_FILES_DIR, PHOTOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
ZHIPU_OCR_API_KEY = os.getenv("ZHIPU_OCR_API_KEY", "")

_deepseek_client: OpenAI | None = None


def get_deepseek_client() -> OpenAI:
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _deepseek_client


def get_zhipu_client():
    from zhipuai import ZhipuAI
    return ZhipuAI(api_key=ZHIPU_OCR_API_KEY)
