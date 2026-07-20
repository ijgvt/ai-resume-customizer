"""统一配置入口，读取 .env 并暴露所有配置项和 API Client 工厂函数。"""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 文件
load_dotenv()

# === 路径常量 ===
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
PROFILE_PATH = DATA_DIR / "profile.json"
OUTPUT_DIR = DATA_DIR / "outputs"
CHROMA_DIR = DATA_DIR / "chroma"
UPLOADS_DIR = DATA_DIR / "uploads"
RESUME_FILES_DIR = DATA_DIR / "resume_files"
FONT_PATH = ROOT_DIR / "fonts" / "NotoSansSC-Regular.ttf"

# 确保目录存在
for d in [DATA_DIR, OUTPUT_DIR, CHROMA_DIR, UPLOADS_DIR, RESUME_FILES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# === API Keys ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
ZHIPU_OCR_API_KEY = os.getenv("ZHIPU_OCR_API_KEY", "")
ZHIPU_EMBEDDING_API_KEY = os.getenv("ZHIPU_EMBEDDING_API_KEY", "")


# === API Client 工厂函数 ===
_deepseek_client: OpenAI | None = None


def get_deepseek_client() -> OpenAI:
    """获取 DeepSeek OpenAI 兼容客户端（单例）。"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _deepseek_client


def get_zhipu_client():
    """获取智谱 SDK 客户端（OCR 和 Embedding 各自用不同 key 实例化）。"""
    from zhipuai import ZhipuAI
    return ZhipuAI(api_key=ZHIPU_OCR_API_KEY)


def get_zhipu_embedding_client():
    """获取智谱 Embedding 专用客户端。"""
    from zhipuai import ZhipuAI
    return ZhipuAI(api_key=ZHIPU_EMBEDDING_API_KEY)
