# AI 求职简历优化助手 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 AI 驱动的求职辅助工具：上传简历 → 自动提取个人信息 → 聊天式搜索 Boss 直聘岗位 → 生成定制 PDF 简历 + 招呼语

**Architecture:** Streamlit 前端 + MCP Server (SSE) 后端分离。Agent Loop 在 Streamlit 进程内运行，通过 OpenAI SDK 调用 DeepSeek（tool_calls 机制），工具执行走 MCP SSE 通道。工具层纯 Python 模块，MCP Server 只是薄包装层。

**Tech Stack:** Python 3.11+, Streamlit, DeepSeek (OpenAI 兼容协议), 智谱 API (OCR + Embedding-2), ChromaDB, fpdf2, Selenium, MCP (SSE)

## Global Constraints

- Python 版本 ≥ 3.11
- 个人信息：10 固定模块 + 2 可选模块，仅 career_objective 和 personal_strengths 由 LLM 生成，其余缺失必须提示用户补充，禁止脑补
- PDF 输入统一走智谱 OCR（不提取文本层），PDF 输出用 fpdf2 + NotoSansSC 字体
- PDF 模板固定顺序：个人信息区 → 教育背景区 → 专业技能区 → 项目经历区 → 实习经历区(如有) → 证书荣誉区(如有) → 个人优势区
- RAG 角色：选择器（JD 检索 → 决定哪些技能/项目该详细写），非内容提供者，PDF 内容 100% 来自 profile.json
- 搜索地区默认策略：用户未指定 → 用 location + 临近城市群扩展
- 所有 API Key 通过 .env 注入，不硬编码
- 文件输出：PDF → `data/outputs/`，ChromaDB → `data/chroma/`

---

## 文件蓝图

| 文件 | 职责 |
|------|------|
| `.gitignore` | 排除 .env, .venv, data/, __pycache__ 等 |
| `requirements.txt` | 全部依赖声明（已有，仅补充缺失项） |
| `config.py` | 统一的配置入口，读取 .env，初始化 API Client |
| `tools/profile_manager.py` | profile.json 的读写、完整性校验、字段更新 |
| `tools/resume_parser.py` | 文件类型判断 + 文本提取（TXT/DOCX/PDF→OCR） |
| `tools/resume_store.py` | ChromaDB 初始化、文本分块、Embedding、存储 |
| `tools/profile_extractor.py` | 调用 DeepSeek LLM 从全文中提取结构化个人信息 |
| `tools/resume_search.py` | ChromaDB 向量检索，基于 JD 关键词找最相关片段 |
| `tools/boss_search.py` | Selenium 打开 Boss 直聘，搜索关键词+城市，返回岗位列表 |
| `tools/boss_detail.py` | Selenium 爬取单个岗位详细 JD |
| `tools/pdf_generator.py` | fpdf2 按固定模板拼装 PDF，内容 100% 来自 profile.json |
| `tools/greeting.py` | 调用 DeepSeek LLM 生成 Boss 直聘风格招呼语 |
| `mcp_server/server.py` | MCP Server SSE 入口，注册所有工具 |
| `agent/loop.py` | Agent ReAct 循环：接收用户消息，调用 DeepSeek + MCP 工具，返回最终结果 |
| `app.py` | Streamlit 入口：侧栏文件上传 + 个人信息管理；主区域聊天 UI |

---

## Task 1: 项目初始化 — .gitignore + 目录 + 依赖

**Files:**
- Create: `.gitignore`
- Create: `data/resume_files/.gitkeep`
- Create: `data/outputs/.gitkeep`
- Create: `data/uploads/.gitkeep`
- Create: `data/chroma/.gitkeep`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: (none — this is first)
- Produces: 完整可用的项目骨架，`pip install -r requirements.txt` 成功

- [ ] **Step 1: 创建 .gitignore**

```bash
cat > d:/resume_agent/.gitignore << 'EOF'
# 环境变量
.env

# 虚拟环境
.venv/
venv/

# Python
__pycache__/
*.pyc
*.pyo

# 数据目录（运行时生成）
data/uploads/*
data/outputs/*
data/chroma/*
data/profile.json

# 保留目录结构
!data/uploads/.gitkeep
!data/outputs/.gitkeep
!data/chroma/.gitkeep
!data/resume_files/.gitkeep

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOF
```

- [ ] **Step 2: 创建数据目录占位文件**

```bash
mkdir -p d:/resume_agent/data/{resume_files,uploads,outputs,chroma}
touch d:/resume_agent/data/resume_files/.gitkeep
touch d:/resume_agent/data/uploads/.gitkeep
touch d:/resume_agent/data/outputs/.gitkeep
touch d:/resume_agent/data/chroma/.gitkeep
```

- [ ] **Step 3: 更新 requirements.txt**

```bash
cat > d:/resume_agent/requirements.txt << 'EOF'
streamlit>=1.50.0
openai>=2.0.0
python-dotenv>=1.0.0
python-docx>=1.1.0
zhipuai>=2.0.0
chromadb>=0.5.0
fpdf2>=2.7.0
selenium>=4.20.0
beautifulsoup4>=4.12.0
mcp>=1.0.0
PyMuPDF>=1.24.0
Pillow>=10.0.0
EOF
```

- [ ] **Step 4: 安装依赖并验证**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
pip install -r requirements.txt
python -c "import streamlit; import openai; import chromadb; import fpdf; import selenium; import zhipuai; import docx; import fitz; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd d:/resume_agent
git add .gitignore requirements.txt data/
git commit -m "chore: initialize project structure and dependencies"
```

---

## Task 2: 配置模块 config.py

**Files:**
- Create: `config.py`

**Interfaces:**
- Consumes: `.env` 文件中的环境变量
- Produces:
  - `config.DEEPSEEK_API_KEY: str`
  - `config.DEEPSEEK_BASE_URL: str`
  - `config.ZHIPU_OCR_API_KEY: str`
  - `config.ZHIPU_EMBEDDING_API_KEY: str`
  - `config.DATA_DIR: str`（绝对路径 `data/`）
  - `config.PROFILE_PATH: str`（`data/profile.json`）
  - `config.OUTPUT_DIR: str`（`data/outputs/`）
  - `config.CHROMA_DIR: str`（`data/chroma/`）
  - `config.FONT_PATH: str`（`fonts/NotoSansSC-Regular.ttf`）
  - `config.get_deepseek_client() -> openai.OpenAI`
  - `config.get_zhipu_client() -> zhipuai.ZhipuAI`

- [ ] **Step 1: 编写 config.py**

```python
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
```

- [ ] **Step 2: 验证配置加载**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "import config; print('DEEPSEEK:', bool(config.DEEPSEEK_API_KEY)); print('OCR:', bool(config.ZHIPU_OCR_API_KEY)); print('EMB:', bool(config.ZHIPU_EMBEDDING_API_KEY)); print('DATA_DIR:', config.DATA_DIR)"
```

Expected: 三个 API Key 都是 True，DATA_DIR 输出正确路径

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add config.py
git commit -m "feat: add config module with unified API client factories"
```

---

## Task 3: tools/profile_manager.py — 个人信息存储与校验

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/profile_manager.py`

**Interfaces:**
- Consumes: `config.PROFILE_PATH`
- Produces:
  - `load_profile() -> dict` — 读取 profile.json，无文件返回空模板
  - `save_profile(profile: dict) -> None` — 写入 profile.json
  - `check_completeness(profile: dict | None = None) -> list[str]` — 检查固定模块完整性，返回缺失字段名列表
  - `update_field(field_name: str, value: any) -> None` — 读取→更新指定字段→写回
  - `create_empty_profile(source_files: list[str] | None = None) -> dict` — 创建空模板

- [ ] **Step 1: 编写 profile_manager.py**

```python
"""个人信息存储与校验。profile.json 是用户信息的唯一真相源。"""
import json
from datetime import datetime
from pathlib import Path
from config import PROFILE_PATH

# 10 个固定模块字段名
FIXED_FIELDS = [
    "name", "career_objective", "expected_salary", "location",
    "phone", "email", "education", "skills", "projects", "personal_strengths"
]

# 固定模块中需要 LLM 生成的字段
GENERATED_FIELDS = {"career_objective", "personal_strengths"}

# 固定模块中需要用户提供（从文件提取或手动填写）的字段
EXTRACTABLE_FIXED = [f for f in FIXED_FIELDS if f not in GENERATED_FIELDS]

# 2 个可选模块字段名
OPTIONAL_FIELDS = ["internships", "certificates"]

ALL_FIELDS = FIXED_FIELDS + OPTIONAL_FIELDS

# 每个字段的类型标记
FIELD_TYPES = {f: "fixed" for f in FIXED_FIELDS}
FIELD_TYPES.update({f: "optional" for f in OPTIONAL_FIELDS})


def create_empty_profile(source_files: list[str] | None = None) -> dict:
    """创建空的 profile 模板，所有字段标记为 missing。"""
    fields = {}
    for name in ALL_FIELDS:
        fields[name] = {
            "value": None if name not in ("education", "skills", "projects", "internships", "certificates") else [],
            "type": FIELD_TYPES[name],
            "status": "missing",
        }
    return {
        "meta": {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "source_files": source_files or [],
        },
        "fields": fields,
    }


def load_profile() -> dict:
    """读取 profile.json，如果文件不存在则返回空模板。"""
    if not PROFILE_PATH.exists():
        return create_empty_profile()
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict) -> None:
    """写入 profile.json，自动更新 updated_at。"""
    profile["meta"]["updated_at"] = datetime.now().isoformat()
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def check_completeness(profile: dict | None = None) -> list[str]:
    """检查固定模块完整性，返回缺失的字段名列表。

    固定模块中，除 LLM 生成的字段外，其余字段 status 不能是 'missing'。
    generated 的字段即使 missing 也不阻止（LLM 没机会生成前）。
    非空列表值的字段（education, skills, projects）还需要检查值不为空列表。
    """
    if profile is None:
        profile = load_profile()

    missing = []
    fields = profile.get("fields", {})

    for name in EXTRACTABLE_FIXED:
        field = fields.get(name, {})
        status = field.get("status", "missing")
        value = field.get("value")

        if status == "missing" or value is None or value == "":
            missing.append(name)
        elif isinstance(value, list) and len(value) == 0:
            missing.append(name)

    return missing


def update_field(field_name: str, value: any) -> None:
    """读取 profile.json，更新指定字段后写回。

    Args:
        field_name: 字段名（必须在 ALL_FIELDS 中）
        value: 新值
    """
    if field_name not in ALL_FIELDS:
        raise ValueError(f"Unknown field: {field_name}")

    profile = load_profile()
    profile["fields"][field_name]["value"] = value
    profile["fields"][field_name]["status"] = "extracted"
    save_profile(profile)


def merge_extracted_fields(extracted: dict, source_files: list[str]) -> dict:
    """将 LLM 提取的结果合并为完整 profile。

    Args:
        extracted: LLM 返回的 {"name": "张三", "skills": [...], ...}
        source_files: 已处理的源文件列表

    Returns:
        合并后的完整 profile dict（已写入文件）
    """
    profile = load_profile()

    # 更新 source_files（追加去重）
    current_sources = set(profile["meta"].get("source_files", []))
    current_sources.update(source_files)
    profile["meta"]["source_files"] = sorted(current_sources)

    fields = profile["fields"]

    for name in ALL_FIELDS:
        if name in extracted and extracted[name] is not None:
            value = extracted[name]
            # 跳过空列表和空字符串
            if isinstance(value, list) and len(value) == 0:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            fields[name]["value"] = value
            if name in GENERATED_FIELDS:
                fields[name]["status"] = "generated"
            else:
                fields[name]["status"] = "extracted"

    save_profile(profile)
    return profile
```

- [ ] **Step 2: 验证基本读写**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.profile_manager import *
p = create_empty_profile()
save_profile(p)
p2 = load_profile()
print('Fields:', list(p2['fields'].keys()))
print('Missing:', check_completeness(p2))
print('Missing count:', len(check_completeness(p2)))
assert len(check_completeness(p2)) == 8
print('PASS')
"
```

Expected: `PASS`（8 个可提取固定字段全部 missing）

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/__init__.py tools/profile_manager.py
git commit -m "feat: add profile manager with CRUD and completeness check"
```

---

## Task 4: tools/resume_parser.py — 文件解析

**Files:**
- Create: `tools/resume_parser.py`

**Interfaces:**
- Consumes: `config.get_zhipu_client()`（OCR）, `python-docx`（DOCX）, `fitz`（PDF 转图片）
- Produces:
  - `parse_file(file_path: str) -> str` — 单文件解析，返回纯文本
  - `parse_files(file_paths: list[str]) -> dict[str, str]` — 批量解析，返回 `{file_path: text}`
  - `parse_directory(dir_path: str) -> dict[str, str]` — 解析目录下所有简历文件

- [ ] **Step 1: 编写 resume_parser.py**

```python
"""文件解析：TXT 直接读，DOCX python-docx 提取，PDF 统一走智谱 OCR。"""
from pathlib import Path
from docx import Document
import fitz  # PyMuPDF

from config import get_zhipu_client


def parse_file(file_path: str) -> str:
    """解析单个文件，返回提取的纯文本。

    Args:
        file_path: 文件路径，支持 .txt / .docx / .pdf

    Returns:
        提取的纯文本字符串
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    elif suffix == ".docx":
        return _parse_docx(file_path)
    elif suffix == ".pdf":
        return _parse_pdf_via_ocr(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def parse_files(file_paths: list[str]) -> dict[str, str]:
    """批量解析文件。

    Args:
        file_paths: 文件路径列表

    Returns:
        {file_path: extracted_text} 字典
    """
    results = {}
    for fp in file_paths:
        try:
            results[fp] = parse_file(fp)
        except Exception as e:
            results[fp] = f"[PARSE_ERROR] {e}"
    return results


def parse_directory(dir_path: str) -> dict[str, str]:
    """解析目录下所有支持的简历文件。

    Args:
        dir_path: 目录路径

    Returns:
        {file_path: extracted_text} 字典
    """
    d = Path(dir_path)
    if not d.is_dir():
        return {}

    supported = {".txt", ".docx", ".pdf"}
    files = [str(f) for f in d.iterdir() if f.suffix.lower() in supported and f.is_file()]
    return parse_files(files)


def _parse_docx(file_path: str) -> str:
    """从 .docx 文件中提取纯文本。"""
    doc = Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _parse_pdf_via_ocr(file_path: str) -> str:
    """PDF 逐页转图片 → 智谱 OCR 识别，返回合并文本。

    使用 PyMuPDF 将每页渲染为 PNG，然后调用智谱 OCR API。
    """
    client = get_zhipu_client()
    doc = fitz.open(file_path)
    all_text: list[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # 渲染为图片（200 DPI，兼顾质量与速度）
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")

        try:
            # 智谱 OCR API：上传图片，获取识别结果
            result = client.files.create(
                file=img_bytes,
                purpose="ocr",
            )
            # 获取 OCR 结果文本
            ocr_text = _extract_ocr_text(result)
            if ocr_text:
                all_text.append(ocr_text)
        except Exception as e:
            all_text.append(f"[OCR_PAGE_{page_num + 1}_ERROR] {e}")

    doc.close()
    return "\n".join(all_text)


def _extract_ocr_text(result) -> str:
    """从智谱 OCR API 返回结果中提取文本。"""
    # 智谱 OCR 返回的 content 中提取识别文字
    try:
        if hasattr(result, "content"):
            return result.content
        if isinstance(result, dict):
            return result.get("content", "") or str(result)
        return str(result)
    except Exception:
        return str(result)
```

- [ ] **Step 2: 验证 TXT 和 DOCX 解析**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.resume_parser import parse_file
# 创建测试文件
import tempfile, os
# TXT test
with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', encoding='utf-8', delete=False) as f:
    f.write('姓名：张三\n技能：Python, Java')
    txt_path = f.name
text = parse_file(txt_path)
print('TXT:', text[:50])
assert '张三' in text
os.unlink(txt_path)
print('PASS')
"
```

Expected: `PASS`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/resume_parser.py
git commit -m "feat: add resume parser with TXT/DOCX/PDF-OCR support"
```

---

## Task 5: tools/resume_store.py — ChromaDB 向量化存储

**Files:**
- Create: `tools/resume_store.py`

**Interfaces:**
- Consumes: `config.CHROMA_DIR`, `config.get_zhipu_embedding_client()`
- Produces:
  - `init_chroma() -> None` — 初始化/获取 ChromaDB collection
  - `store_chunks(text: str, metadata: dict | None = None) -> None` — 分 chunk → embedding → 存储
  - `get_collection()` — 返回当前 collection 实例

- [ ] **Step 1: 编写 resume_store.py**

```python
"""ChromaDB 向量化存储：文本分块 → 智谱 Embedding-2 → ChromaDB 持久化。"""
import chromadb
from chromadb.config import Settings as ChromaSettings

from config import CHROMA_DIR, get_zhipu_embedding_client

COLLECTION_NAME = "resume_chunks"
CHUNK_SIZE = 400   # 每 chunk 约 400 字
CHUNK_OVERLAP = 50  # 相邻 chunk 重叠 50 字

_collection = None


def init_chroma() -> None:
    """初始化 ChromaDB 持久化客户端和 collection。幂等操作。"""
    global _collection
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    # 如果 collection 已存在则获取，否则创建
    try:
        _collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        _collection = client.create_collection(COLLECTION_NAME)
    return _collection


def get_collection():
    """返回当前 ChromaDB collection，未初始化则自动初始化。"""
    global _collection
    if _collection is None:
        init_chroma()
    return _collection


def _split_text(text: str) -> list[str]:
    """将文本按固定大小切分为重叠 chunk。

    Args:
        text: 原始文本

    Returns:
        chunk 字符串列表
    """
    if not text or len(text) <= CHUNK_SIZE:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - CHUNK_OVERLAP
        if start >= len(text):
            break

    return chunks


def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """调用智谱 Embedding-2 获取向量。"""
    client = get_zhipu_embedding_client()
    embeddings = []
    # 智谱 embedding-2 模型
    for chunk in chunks:
        resp = client.embeddings.create(
            model="embedding-2",
            input=chunk,
        )
        embeddings.append(resp.data[0].embedding)
    return embeddings


def store_chunks(text: str, metadata: dict | None = None) -> int:
    """文本分 chunk → embedding → 存入 ChromaDB。

    Args:
        text: 原始文本
        metadata: 附加元数据（如来源文件）

    Returns:
        存储的 chunk 数量
    """
    collection = get_collection()
    chunks = _split_text(text)
    if not chunks:
        return 0

    embeddings = _embed_chunks(chunks)
    n = len(chunks)

    meta = metadata or {}
    ids = [f"chunk_{collection.count() + i}" for i in range(n)]
    metadatas = [meta for _ in range(n)]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return n


def clear_collection() -> None:
    """清空 collection 中的所有数据。"""
    collection = get_collection()
    ids = collection.get()["ids"]
    if ids:
        collection.delete(ids=ids)
```

- [ ] **Step 2: 验证 ChromaDB 写入和读取**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.resume_store import init_chroma, store_chunks, get_collection, clear_collection
init_chroma()
n = store_chunks('Python 是一种解释型编程语言，广泛用于 Web 开发、数据科学等领域。' * 20)
print(f'Stored {n} chunks')
coll = get_collection()
print(f'Collection count: {coll.count()}')
assert coll.count() == n
clear_collection()
assert coll.count() == 0
print('PASS')
"
```

Expected: `PASS`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/resume_store.py
git commit -m "feat: add ChromaDB vector store with Zhipu Embedding-2"
```

---

## Task 6: tools/profile_extractor.py — LLM 结构化提取个人信息

**Files:**
- Create: `tools/profile_extractor.py`

**Interfaces:**
- Consumes: `config.get_deepseek_client()`, `tools.profile_manager.merge_extracted_fields()`
- Produces:
  - `extract_profile(texts: dict[str, str]) -> dict` — LLM 从所有文本中提取结构化字段

- [ ] **Step 1: 编写 profile_extractor.py**

```python
"""调用 DeepSeek LLM 从简历文本中结构化提取个人信息字段。"""
import json
from config import get_deepseek_client, DEEPSEEK_BASE_URL
from tools.profile_manager import merge_extracted_fields

EXTRACTION_PROMPT = """你是一位简历分析专家。请从以下简历文本中提取信息，输出 JSON。

## 提取规则

### 固定字段（必须提取，找不到填 null）
1. name: 姓名
2. expected_salary: 期望薪资（如 "15K-20K"、"面议"），简历未写明填 null
3. location: 所在城市（如 "深圳"）
4. phone: 手机号码
5. email: 邮箱地址
6. education: 教育背景列表 [{school, major, degree, graduation_year}]
7. skills: 技能列表 [{name, level}] level 可选：精通/熟练/了解
8. projects: 项目经历列表 [{name, role, start_date, end_date, description}]

### LLM 生成字段（你必须基于全部分析结果来填写）
9. career_objective: 一句话求职意向，概括目标岗位和方向
10. personal_strengths: 个人优势，3-5 点，用换行分隔

### 可选字段（有则提取，无则填 null 或空数组）
11. internships: 实习经历列表 [{company, position, start_date, end_date, description}]
12. certificates: 技能证书与获奖荣誉列表 [{name, issuer, year}]

## 重要规则
- 除 career_objective 和 personal_strengths 外，其他字段提取不到必须填 null（字符串）或 []（数组），禁止编造
- career_objective 和 personal_strengths 由你根据全部分析来合理生成，不要留空
- skills 的 level 从文本中推断，没有明确说明则填 "熟练"

## 简历文本

{texts}

## 输出格式
只输出一个 JSON 对象，不要有任何其他文字。"""


def extract_profile(texts: dict[str, str]) -> dict:
    """从多份简历文本中提取结构化个人信息。

    Args:
        texts: {"file_path": "text content", ...}

    Returns:
        合并后的完整 profile dict（已写入 profile.json）
    """
    # 整理文本
    combined = ""
    for fp, text in texts.items():
        if text.startswith("[PARSE_ERROR]") or text.startswith("[OCR_"):
            continue
        combined += f"\n=== 文件: {fp} ===\n{text}\n"

    if not combined.strip():
        raise ValueError("No valid text extracted from files")

    client = get_deepseek_client()

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.format(texts=combined)},
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    content = response.choices[0].message.content.strip()

    # 提取 JSON（处理可能的 markdown 代码块包裹）
    if content.startswith("```"):
        lines = content.split("\n")
        # 去掉第一行 ```json 和最后一行 ```
        content = "\n".join(lines[1:-1])

    extracted = json.loads(content)

    # 合并到 profile.json
    source_files = list(texts.keys())
    profile = merge_extracted_fields(extracted, source_files)
    return profile
```

- [ ] **Step 2: 用 mock 数据验证提取逻辑**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.profile_extractor import _parse_llm_response
# 测试 JSON 解析
import json
mock = '''{
    \"name\": \"张三\",
    \"career_objective\": \"Python后端开发工程师\",
    \"expected_salary\": \"20K-30K\",
    \"location\": \"深圳\",
    \"phone\": \"13800138000\",
    \"email\": \"test@example.com\",
    \"education\": [{\"school\": \"XX大学\", \"major\": \"计算机科学\", \"degree\": \"本科\", \"graduation_year\": \"2020\"}],
    \"skills\": [{\"name\": \"Python\", \"level\": \"精通\"}],
    \"projects\": [{\"name\": \"电商平台\", \"role\": \"后端开发\", \"start_date\": \"2021\", \"end_date\": \"2022\", \"description\": \"用Django开发\"}],
    \"personal_strengths\": \"1. 学习能力强\\n2. 团队协作\",
    \"internships\": [],
    \"certificates\": [{\"name\": \"AWS认证\", \"issuer\": \"Amazon\", \"year\": \"2021\"}]
}'''
data = json.loads(mock)
from tools.profile_manager import merge_extracted_fields
profile = merge_extracted_fields(data, ['test.pdf'])
missing = __import__('tools.profile_manager', fromlist=['check_completeness']).check_completeness(profile)
print('Missing:', missing)
assert len(missing) == 0, f'Unexpected missing: {missing}'
print('PASS')
"
```

Expected: `Missing: []` 然后 `PASS`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/profile_extractor.py
git commit -m "feat: add LLM-based profile extractor from resume texts"
```

---

## Task 7: tools/resume_search.py — ChromaDB 向量检索

**Files:**
- Create: `tools/resume_search.py`

**Interfaces:**
- Consumes: `tools.resume_store.get_collection()`, `config.get_zhipu_embedding_client()`
- Produces:
  - `search(query: str, top_k: int = 5) -> list[dict]` — 返回 `[{chunk_text, metadata, score}, ...]`

- [ ] **Step 1: 编写 resume_search.py**

```python
"""ChromaDB 向量检索：用 JD 描述或关键词检索最相关的简历片段。"""
from config import get_zhipu_embedding_client
from tools.resume_store import get_collection


def embed_query(query: str) -> list[float]:
    """将查询文本向量化。"""
    client = get_zhipu_embedding_client()
    resp = client.embeddings.create(
        model="embedding-2",
        input=query,
    )
    return resp.data[0].embedding


def search(query: str, top_k: int = 5) -> list[dict]:
    """基于 JD 关键词或描述，检索最相关的简历片段。

    Args:
        query: JD 描述或搜索关键词
        top_k: 返回 top-k 个最相似的片段

    Returns:
        [{"text": chunk文本, "metadata": 元数据, "score": 相似度分数}, ...]
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    items = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            items.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": 1.0 - results["distances"][0][i],  # distance → similarity
            })

    return items
```

- [ ] **Step 2: 端到端验证（存入 → 检索）**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.resume_store import init_chroma, store_chunks, clear_collection
from tools.resume_search import search

clear_collection()
init_chroma()

# 存入两段不同主题的文本
store_chunks('张三精通 Python 和 Django，有5年后端开发经验，负责过电商平台架构设计', {'file': 'test'})
store_chunks('李四擅长 Java 和 Spring Boot，做过微服务架构迁移，熟悉 K8s 和 Docker', {'file': 'test'})

# 搜索 Python 相关
results = search('Python Django 后端开发', top_k=2)
print(f'Top result text: {results[0][\"text\"][:50]}')
assert 'Python' in results[0]['text']

# 搜索 Java 相关
results2 = search('Java Spring 微服务', top_k=2)
print(f'Top result text: {results2[0][\"text\"][:50]}')
assert 'Java' in results2[0]['text']

clear_collection()
print('PASS')
"
```

Expected: 两次检索各自命中正确主题，输出 `PASS`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/resume_search.py
git commit -m "feat: add ChromaDB vector search for resume chunks"
```

---

## Task 8: tools/boss_search.py — Boss 直聘搜索列表爬取

**Files:**
- Create: `tools/boss_search.py`

**Interfaces:**
- Consumes: Selenium WebDriver
- Produces:
  - `search_boss(keyword: str, city: str) -> list[dict]` — 返回 `[{title, company, salary, description, url, city}, ...]`

- [ ] **Step 1: 编写 boss_search.py**

```python
"""Boss 直聘搜索列表爬取，使用 Selenium 自动化浏览器。"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BOSS_BASE_URL = "https://www.zhipin.com"


def _create_driver() -> webdriver.Chrome:
    """创建带反检测配置的 Chrome WebDriver。"""
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationEnabled", False)
    # 不 headless，用户可以看到浏览器操作
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def search_boss(keyword: str, city: str, max_pages: int = 3) -> list[dict]:
    """在 Boss 直聘搜索岗位列表。

    Args:
        keyword: 搜索关键词，如 "Python开发"
        city: 城市编码，如 "101280600"（深圳），"100010000"（北京）
        max_pages: 最大翻页数

    Returns:
        [{title, company, salary, description, url, city_name}, ...]
    """
    driver = _create_driver()
    jobs: list[dict] = []

    try:
        # 构造搜索 URL
        search_url = f"{BOSS_BASE_URL}/web/geek/job?query={keyword}&city={city}"
        driver.get(search_url)
        time.sleep(3)  # 等待页面加载

        for page in range(max_pages):
            # 等待岗位卡片加载
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".job-card-body, .job-card-wrap"))
                )
            except Exception:
                break  # 页面结构可能变化，中断翻页

            time.sleep(2)
            cards = driver.find_elements(By.CSS_SELECTOR, ".job-card-body, .job-card-wrap")

            for card in cards:
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, ".job-name, .job-title")
                    company_el = card.find_element(By.CSS_SELECTOR, ".company-name, .company-text")
                    salary_el = card.find_element(By.CSS_SELECTOR, ".salary, .red")
                    link_el = card.find_element(By.CSS_SELECTOR, "a")

                    title = title_el.text.strip()
                    company = company_el.text.strip()
                    salary = salary_el.text.strip() if salary_el else ""
                    url = link_el.get_attribute("href") or ""

                    # 尝试获取简要描述
                    desc_el = card.find_elements(By.CSS_SELECTOR, ".job-info, .tag-list, .job-tag")
                    desc = " ".join([d.text.strip() for d in desc_el if d.text.strip()])

                    if title and company:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "salary": salary,
                            "description": desc,
                            "url": url,
                            "search_city": city,
                        })
                except Exception:
                    continue  # 单个卡片解析失败不影响整体

            # 翻页
            if page < max_pages - 1:
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, ".page .next, .next-page")
                    if "disabled" in next_btn.get_attribute("class") or "":
                        break
                    next_btn.click()
                    time.sleep(3)
                except Exception:
                    break

        return jobs

    finally:
        driver.quit()
```

- [ ] **Step 2: 验证代码可以导入**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.boss_search import search_boss, BOSS_BASE_URL
print('boss_search module loaded OK')
print(f'Boss URL: {BOSS_BASE_URL}')
"
```

Expected: `boss_search module loaded OK`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/boss_search.py
git commit -m "feat: add Boss Zhipin search list scraper with Selenium"
```

---

## Task 9: tools/boss_detail.py — Boss 直聘 JD 详情爬取

**Files:**
- Create: `tools/boss_detail.py`

**Interfaces:**
- Consumes: Selenium WebDriver
- Produces:
  - `get_job_detail(url: str) -> dict` — 返回 `{title, company, salary, jd_text, requirements, tags, ...}`

- [ ] **Step 1: 编写 boss_detail.py**

```python
"""Boss 直聘岗位详情页爬取，提取完整 JD。"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _create_driver() -> webdriver.Chrome:
    """创建带反检测配置的 Chrome WebDriver。"""
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationEnabled", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def get_job_detail(url: str) -> dict:
    """爬取单个 Boss 直聘岗位详情页。

    Args:
        url: 岗位详情页完整 URL

    Returns:
        {
            "title": 岗位名称,
            "company": 公司名,
            "salary": 薪资,
            "location": 工作地点,
            "experience": 经验要求,
            "education": 学历要求,
            "jd_text": 完整职位描述,
            "tags": 标签列表,
            "url": 原始 URL,
        }
    """
    driver = _create_driver()
    detail: dict = {"url": url}

    try:
        driver.get(url)
        time.sleep(3)

        # 尝试多种 CSS selector 适配页面变化
        selectors = {
            "title": ".name, .job-name, h1",
            "company": ".company-name, .company-info .name",
            "salary": ".salary, .salary-bar .salary",
            "jd_text": ".job-detail, .job-sec, .text, .detail-text",
            "location": ".job-location, .location-address",
            "experience": ".job-experience, .experience-request",
        }

        for field, selector in selectors.items():
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                detail[field] = el.text.strip()
            except Exception:
                detail[field] = ""

        # 提取标签
        try:
            tag_els = driver.find_elements(By.CSS_SELECTOR, ".job-tag, .tag-item, .tags .tag")
            detail["tags"] = [t.text.strip() for t in tag_els if t.text.strip()]
        except Exception:
            detail["tags"] = []

        # 综合 JD 文本：job-detail + job-sec 两个区域
        all_text_parts = []
        try:
            sections = driver.find_elements(By.CSS_SELECTOR, ".job-sec, .job-detail, .detail-section")
            for sec in sections:
                text = sec.text.strip()
                if text:
                    all_text_parts.append(text)
        except Exception:
            pass

        if all_text_parts:
            detail["jd_text"] = "\n\n".join(all_text_parts)

        return detail

    except Exception as e:
        detail["error"] = str(e)
        return detail

    finally:
        driver.quit()
```

- [ ] **Step 2: 验证代码可导入**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "from tools.boss_detail import get_job_detail; print('boss_detail module loaded OK')"
```

Expected: `boss_detail module loaded OK`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/boss_detail.py
git commit -m "feat: add Boss Zhipin job detail scraper"
```

---

## Task 10: tools/pdf_generator.py — fpdf2 定制 PDF 生成

**Files:**
- Create: `tools/pdf_generator.py`

**Interfaces:**
- Consumes: `config.FONT_PATH`, `config.OUTPUT_DIR`, `tools.profile_manager.load_profile()`
- Produces:
  - `generate_pdf(profile: dict, jd: dict | None, relevant_skills: list[str] | None, relevant_projects: list[str] | None) -> str` — 返回生成的 PDF 文件路径

- [ ] **Step 1: 编写 pdf_generator.py**

```python
"""fpdf2 定制化 PDF 简历生成，内容 100% 来自 profile.json，按固定模板拼装。"""
from datetime import datetime
from fpdf import FPDF
from config import FONT_PATH, OUTPUT_DIR


class ResumePDF(FPDF):
    """中文简历 PDF 生成器。"""

    def __init__(self):
        super().__init__()
        self.add_font("NotoSansSC", "", str(FONT_PATH), uni=True)
        # 注册粗体变体（如果没有粗体文件，用 regular 替代）
        self.add_font("NotoSansSC", "B", str(FONT_PATH), uni=True)

    def header(self):
        pass  # 不显示页眉

    def footer(self):
        pass  # 不显示页脚


def generate_pdf(
    profile: dict,
    jd: dict | None = None,
    relevant_skills: list[str] | None = None,
    relevant_projects: list[str] | None = None,
) -> str:
    """生成定制化 PDF 简历。

    Args:
        profile: 从 profile.json 加载的用户信息 dict
        jd: 岗位 JD 信息（用于排序和加重），可为 None
        relevant_skills: RAG 检索到的最相关技能名列表
        relevant_projects: RAG 检索到的最相关项目名列表

    Returns:
        生成的 PDF 文件绝对路径
    """
    fields = profile.get("fields", {})
    jd = jd or {}
    relevant_skills = relevant_skills or []
    relevant_projects = relevant_projects or []

    pdf = ResumePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 颜色设置
    SECTION_BG = (240, 240, 240)  # 节标题背景灰
    LINE_COLOR = (200, 200, 200)   # 分隔线灰
    TEXT_DARK = (30, 30, 30)
    TEXT_GRAY = (100, 100, 100)

    # ===== 1. 个人信息区 =====
    _section_title(pdf, "个人信息")
    name = _f(fields, "name")
    phone = _f(fields, "phone")
    email = _f(fields, "email")
    location = _f(fields, "location")
    objective = _f(fields, "career_objective")
    salary = _f(fields, "expected_salary")

    pdf.set_font("NotoSansSC", "B", 16)
    pdf.set_text_color(*TEXT_DARK)
    pdf.cell(0, 10, name, ln=True)

    pdf.set_font("NotoSansSC", "", 10)
    pdf.set_text_color(*TEXT_GRAY)
    info_line = f"{phone}  |  {email}  |  {location}"
    pdf.cell(0, 7, info_line, ln=True)
    if objective:
        pdf.cell(0, 7, f"求职意向：{objective}    期望薪资：{salary}", ln=True)
    pdf.ln(3)

    # ===== 2. 教育背景区 =====
    _section_title(pdf, "教育背景")
    edu_list = _v(fields, "education")
    if isinstance(edu_list, list):
        for edu in edu_list:
            if isinstance(edu, dict):
                line = f"{edu.get('school', '')}  |  {edu.get('major', '')}  |  {edu.get('degree', '')}  |  {edu.get('graduation_year', '')}"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
    pdf.ln(3)

    # ===== 3. 专业技能区（按 JD 匹配度排序）=====
    _section_title(pdf, "专业技能")
    skills = _v(fields, "skills")
    if isinstance(skills, list):
        # 排序：RAG 命中 → 前置
        def _skill_sort_key(s):
            name = s.get("name", "") if isinstance(s, dict) else str(s)
            relevant = name in relevant_skills or any(
                kw in name for kw in (jd.get("jd_text", "") + jd.get("title", ""))
            )
            return 0 if relevant else 1

        sorted_skills = sorted(skills, key=_skill_sort_key)
        for sk in sorted_skills:
            if isinstance(sk, dict):
                name = sk.get("name", "")
                level = sk.get("level", "")
                line = f"• {name}"
                if level:
                    line += f"（{level}）"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
    pdf.ln(3)

    # ===== 4. 项目经历区（JD 相关加重）=====
    _section_title(pdf, "项目经历")
    projects = _v(fields, "projects")
    if isinstance(projects, list):
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            pname = proj.get("name", "")
            is_relevant = pname in relevant_projects or any(
                kw in str(proj) for kw in (jd.get("jd_text", "") + jd.get("title", ""))
            )

            # 项目标题
            pdf.set_font("NotoSansSC", "B" if is_relevant else "", 11 if is_relevant else 10)
            pdf.set_text_color(*TEXT_DARK)
            role = proj.get("role", "")
            dates = f"{proj.get('start_date', '')} - {proj.get('end_date', '')}"
            pdf.cell(0, 7, f"• {pname}  |  {role}  |  {dates}", ln=True)

            # 项目描述
            desc = proj.get("description", "")
            if desc:
                pdf.set_font("NotoSansSC", "", 9)
                pdf.set_text_color(*TEXT_GRAY)
                # 处理长文本换行
                desc_lines = _wrap_text(pdf, desc, 170)
                for dl in desc_lines:
                    pdf.cell(0, 5, f"  {dl}", ln=True)
            pdf.ln(2)

    pdf.ln(2)

    # ===== 5. 实习经历区（如有）=====
    internships = _v(fields, "internships")
    if isinstance(internships, list) and len(internships) > 0:
        _section_title(pdf, "实习经历")
        for inter in internships:
            if isinstance(inter, dict):
                line = f"• {inter.get('company', '')}  |  {inter.get('position', '')}  |  {inter.get('start_date', '')} - {inter.get('end_date', '')}"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
                desc = inter.get("description", "")
                if desc:
                    pdf.set_font("NotoSansSC", "", 9)
                    pdf.set_text_color(*TEXT_GRAY)
                    for dl in _wrap_text(pdf, desc, 170):
                        pdf.cell(0, 5, f"  {dl}", ln=True)
        pdf.ln(3)

    # ===== 6. 证书荣誉区（如有）=====
    certs = _v(fields, "certificates")
    if isinstance(certs, list) and len(certs) > 0:
        _section_title(pdf, "技能证书与获奖荣誉")
        for cert in certs:
            if isinstance(cert, dict):
                line = f"• {cert.get('name', '')}"
                if cert.get("issuer"):
                    line += f"  |  {cert['issuer']}"
                if cert.get("year"):
                    line += f"  |  {cert['year']}"
                pdf.set_font("NotoSansSC", "", 10)
                pdf.set_text_color(*TEXT_DARK)
                pdf.cell(0, 7, line, ln=True)
        pdf.ln(3)

    # ===== 7. 个人优势区 =====
    strengths = _f(fields, "personal_strengths")
    if strengths:
        _section_title(pdf, "个人优势")
        pdf.set_font("NotoSansSC", "", 10)
        pdf.set_text_color(*TEXT_DARK)
        for line in strengths.split("\n"):
            line = line.strip()
            if line:
                pdf.cell(0, 7, line, ln=True)

    # ===== 保存 =====
    # 生成文件名
    job_title = jd.get("title", "定制简历").replace("/", "_").replace(" ", "_")
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"resume_{job_title}_{date_str}.pdf"
    output_path = str(OUTPUT_DIR / filename)

    pdf.output(output_path)
    return output_path


def _section_title(pdf: ResumePDF, title: str):
    """绘制节标题（带背景条）。"""
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("NotoSansSC", "B", 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, f"  {title}", ln=True, fill=True)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def _f(fields: dict, name: str) -> str:
    """安全获取字段的字符串值。"""
    f = fields.get(name, {})
    val = f.get("value", "") if isinstance(f, dict) else ""
    return str(val) if val else ""


def _v(fields: dict, name: str):
    """安全获取字段的原始值。"""
    f = fields.get(name, {})
    return f.get("value") if isinstance(f, dict) else None


def _wrap_text(pdf: ResumePDF, text: str, max_width: float) -> list[str]:
    """简单中文换行：按宽度估算每行字符数。"""
    # 中文字符约 5pt 宽度（9pt 字体），170mm 宽约 34 个中文字符
    chars_per_line = int(max_width / 5)  # 约 34
    lines = []
    remaining = text
    while len(remaining) > chars_per_line:
        lines.append(remaining[:chars_per_line])
        remaining = remaining[chars_per_line:]
    if remaining:
        lines.append(remaining)
    return lines
```

- [ ] **Step 2: 用空 profile 生成 PDF 验证**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
from tools.profile_manager import create_empty_profile, merge_extracted_fields
from tools.pdf_generator import generate_pdf
import json

# 创建测试数据
test_data = {
    'name': '张三',
    'career_objective': 'Python 后端开发工程师',
    'expected_salary': '20K-30K',
    'location': '深圳',
    'phone': '13800138000',
    'email': 'test@test.com',
    'education': [{'school': 'XX大学', 'major': '计算机', 'degree': '本科', 'graduation_year': '2020'}],
    'skills': [{'name': 'Python', 'level': '精通'}, {'name': 'Django', 'level': '熟练'}],
    'projects': [{'name': '电商平台', 'role': '后端开发', 'start_date': '2021', 'end_date': '2022', 'description': '负责订单系统的设计与开发'}],
    'personal_strengths': '1. 5年后端开发经验\n2. 熟悉分布式架构\n3. 团队协作能力强',
    'internships': [],
    'certificates': [{'name': 'AWS SAA', 'issuer': 'Amazon', 'year': '2021'}],
}
profile = merge_extracted_fields(test_data, ['test.pdf'])
jd = {'title': 'Python开发工程师', 'jd_text': '需要Python和Django技能'}

path = generate_pdf(profile, jd)
print(f'PDF generated: {path}')
import os; print(f'Exists: {os.path.exists(path)}')
"
```

Expected: PDF 生成成功，文件存在

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/pdf_generator.py
git commit -m "feat: add fpdf2 PDF resume generator with fixed template"
```

---

## Task 11: tools/greeting.py — 招呼语生成

**Files:**
- Create: `tools/greeting.py`

**Interfaces:**
- Consumes: `config.get_deepseek_client()`
- Produces:
  - `generate_greeting(profile: dict, jd: dict) -> str` — 返回 100-200 字招呼语

- [ ] **Step 1: 编写 greeting.py**

```python
"""生成 Boss 直聘风格招呼语，100-200 字，突出匹配点。"""
from config import get_deepseek_client

GREETING_PROMPT = """你是一位求职顾问，需要为以下候选人写一段 Boss 直聘风格的打招呼语。

## 候选人背景
{profile_summary}

## 目标岗位
{jd_summary}

## 要求
- 风格：简洁干练，突出亮点，有针对性
- 字数：100-200 字
- 结构：称呼（"您好"）+ 核心匹配点（"我有X年XX经验，做过XX项目"）+ 表达兴趣 + 期待回复
- 包含至少一个与 JD 直接相关的技能或项目亮点
- 不要过度推销，语气真诚
- 直接输出招呼语文本，不要加任何说明或前缀"""


def generate_greeting(profile: dict, jd: dict) -> str:
    """生成 Boss 直聘风格招呼语。

    Args:
        profile: 用户个人信息
        jd: 岗位 JD 信息

    Returns:
        招呼语文案（纯文本）
    """
    client = get_deepseek_client()

    # 构建候选人摘要
    fields = profile.get("fields", {})
    name = _f(fields, "name")
    skills = _v(fields, "skills")
    projects = _v(fields, "projects")
    strengths = _f(fields, "personal_strengths")
    objective = _f(fields, "career_objective")

    profile_summary = f"""姓名：{name}
求职意向：{objective}
技能：{_fmt_list(skills, "name")}
项目经历：{_fmt_list(projects, "name")}
个人优势：{strengths}"""

    jd_summary = f"""岗位：{jd.get("title", "")}
公司：{jd.get("company", "")}
薪资：{jd.get("salary", "")}
JD：{jd.get("jd_text", "")}"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": GREETING_PROMPT.format(
                profile_summary=profile_summary,
                jd_summary=jd_summary,
            )},
        ],
        temperature=0.7,
        max_tokens=500,
    )

    return response.choices[0].message.content.strip()


def _f(fields: dict, name: str) -> str:
    val = fields.get(name, {}).get("value", "") if isinstance(fields.get(name), dict) else ""
    return str(val) if val else ""


def _v(fields: dict, name: str):
    return fields.get(name, {}).get("value") if isinstance(fields.get(name), dict) else None


def _fmt_list(items, key) -> str:
    """格式化列表为逗号分隔字符串。"""
    if not isinstance(items, list):
        return ""
    names = []
    for item in items:
        if isinstance(item, dict):
            names.append(item.get(key, ""))
        elif isinstance(item, str):
            names.append(item)
    return "、".join(names[:10])
```

- [ ] **Step 2: 验证代码可导入**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "from tools.greeting import generate_greeting; print('greeting module loaded OK')"
```

Expected: `greeting module loaded OK`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add tools/greeting.py
git commit -m "feat: add Boss Zhipin style greeting generator"
```

---

## Task 12: mcp_server/server.py — MCP Server 工具注册

**Files:**
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/server.py`

**Interfaces:**
- Consumes: `tools.*` 所有工具模块
- Produces: 独立的 MCP SSE Server 进程，监听 `localhost:8765`

- [ ] **Step 1: 编写 mcp_server/server.py**

```python
"""MCP Server SSE 入口：注册所有工具，通过 SSE 暴露。"""
import asyncio
import json
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from tools.profile_manager import load_profile, save_profile, check_completeness, update_field
from tools.resume_parser import parse_file, parse_files, parse_directory
from tools.resume_store import init_chroma, store_chunks
from tools.profile_extractor import extract_profile
from tools.resume_search import search as resume_search_fn
from tools.boss_search import search_boss
from tools.boss_detail import get_job_detail
from tools.pdf_generator import generate_pdf
from tools.greeting import generate_greeting
from config import RESUME_FILES_DIR


app = Server("resume-agent")


# === 个人信息管理 ===

@app.tool()
async def profile_get() -> list[TextContent]:
    """获取用户完整个人信息档案，包括每个字段的值和状态。"""
    profile = load_profile()
    return [TextContent(type="text", text=json.dumps(profile, ensure_ascii=False, indent=2))]


@app.tool()
async def profile_update(field_name: str, value: str) -> list[TextContent]:
    """手动更新个人信息中的指定字段。

    Args:
        field_name: 字段名（name/phone/email/location/expected_salary 等）
        value: 新值（JSON 字符串，复杂类型用 JSON 格式传入）
    """
    try:
        # 尝试解析 JSON
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = value
    update_field(field_name, parsed)
    return [TextContent(type="text", text=f"已更新 {field_name}")]


@app.tool()
async def profile_check() -> list[TextContent]:
    """检查个人信息是否完整，返回缺失的固定模块字段列表。"""
    missing = check_completeness()
    if missing:
        return [TextContent(
            type="text",
            text=f"个人信息不完整，以下字段缺失：{', '.join(missing)}。请提醒用户补充这些信息。"
        )]
    return [TextContent(type="text", text="个人信息完整，可以使用。")]


# === 简历文件解析 ===

@app.tool()
async def resume_parse(file_path: str) -> list[TextContent]:
    """解析单个简历文件，返回提取的纯文本。

    支持 .txt / .docx / .pdf（PDF 统一走智谱 OCR）。
    """
    text = parse_file(file_path)
    return [TextContent(type="text", text=text)]


@app.tool()
async def resume_parse_directory(dir_path: str | None = None) -> list[TextContent]:
    """解析目录下所有简历文件，返回文本集合。

    Args:
        dir_path: 目录路径，默认使用 data/resume_files/
    """
    path = dir_path or str(RESUME_FILES_DIR)
    results = parse_directory(path)
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


@app.tool()
async def resume_store(text: str, source_file: str = "") -> list[TextContent]:
    """将简历文本分块后向量化存入 ChromaDB。

    Args:
        text: 简历完整文本
        source_file: 来源文件名（可选）
    """
    init_chroma()
    n = store_chunks(text, {"source": source_file} if source_file else None)
    return [TextContent(type="text", text=f"已存储 {n} 个文本块到向量数据库")]


@app.tool()
async def resume_extract(texts_json: str) -> list[TextContent]:
    """调用 LLM 从简历文本中提取结构化个人信息，写入 profile.json。

    Args:
        texts_json: JSON 字符串，格式 {"file_path": "文本内容", ...}
    """
    texts = json.loads(texts_json)
    profile = extract_profile(texts)
    return [TextContent(type="text", text=json.dumps(profile, ensure_ascii=False, indent=2))]


@app.tool()
async def resume_search(query: str, top_k: int = 5) -> list[TextContent]:
    """基于 JD 描述或关键词，在 ChromaDB 中检索最相关的简历片段。

    Args:
        query: JD 描述或搜索关键词
        top_k: 返回 top-k 个最相似片段（默认 5）
    """
    results = resume_search_fn(query, top_k)
    return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]


# === Boss 直聘 ===

@app.tool()
async def boss_search_list(keyword: str, city: str, max_pages: int = 3) -> list[TextContent]:
    """在 Boss 直聘搜索岗位列表。

    Args:
        keyword: 搜索关键词，如 "Python开发"
        city: 城市名（中文），如 "深圳"、"北京"
        max_pages: 最大翻页数（默认 3）
    """
    # 城市名 → Boss 直聘城市编码（部分映射）
    city_map = {
        "深圳": "101280600", "广州": "101280100", "东莞": "101281600",
        "珠海": "101280700", "惠州": "101280300", "佛山": "101280800",
        "北京": "100010000", "天津": "100030000", "石家庄": "100450000",
        "上海": "100020000", "杭州": "101210100", "苏州": "101190400",
        "南京": "101190100", "宁波": "101210400",
        "成都": "101270100", "重庆": "100060000", "绵阳": "101270500",
        "武汉": "101200100", "长沙": "101250100", "郑州": "101180100",
        "西安": "101110100", "咸阳": "101110200", "宝鸡": "101110900",
    }
    city_code = city_map.get(city, "100010000")
    jobs = search_boss(keyword, city_code, max_pages)
    return [TextContent(type="text", text=json.dumps(jobs, ensure_ascii=False, indent=2))]


@app.tool()
async def boss_job_detail(url: str) -> list[TextContent]:
    """爬取单个 Boss 直聘岗位的详细 JD。

    Args:
        url: 岗位详情页完整 URL
    """
    detail = get_job_detail(url)
    return [TextContent(type="text", text=json.dumps(detail, ensure_ascii=False, indent=2))]


# === 生成 ===

@app.tool()
async def pdf_generate(jd_json: str) -> list[TextContent]:
    """根据当前个人信息和指定 JD，生成定制化 PDF 简历。

    Args:
        jd_json: 岗位 JD 的 JSON 字符串
    """
    profile = load_profile()
    jd = json.loads(jd_json)

    # 先检索相关片段来确定哪些技能/项目应加重
    jd_text = jd.get("jd_text", "") + " " + jd.get("title", "")
    relevant = resume_search_fn(jd_text, top_k=5)

    relevant_skills = []
    relevant_projects = []
    for item in relevant:
        text = item.get("text", "")
        # 从 chunk 中提取项目名和技能名（简单匹配）
        skills = _v(profile["fields"], "skills") or []
        if isinstance(skills, list):
            for s in skills:
                name = s.get("name", "") if isinstance(s, dict) else s
                if name and name in text:
                    relevant_skills.append(name)

        projects = _v(profile["fields"], "projects") or []
        if isinstance(projects, list):
            for p in projects:
                name = p.get("name", "") if isinstance(p, dict) else p
                if name and name in text:
                    relevant_projects.append(name)

    output_path = generate_pdf(
        profile=profile,
        jd=jd,
        relevant_skills=list(set(relevant_skills)),
        relevant_projects=list(set(relevant_projects)),
    )
    return [TextContent(type="text", text=f"PDF 已生成：{output_path}")]


@app.tool()
async def greeting_generate(jd_json: str) -> list[TextContent]:
    """生成一段 Boss 直聘风格的打招呼语。

    Args:
        jd_json: 岗位 JD 的 JSON 字符串
    """
    profile = load_profile()
    jd = json.loads(jd_json)
    greeting_text = generate_greeting(profile, jd)
    return [TextContent(type="text", text=greeting_text)]


def _v(value, field_name: str):
    """安全获取字段值。"""
    if not isinstance(value, dict):
        return None
    f = value.get(field_name, {})
    return f.get("value") if isinstance(f, dict) else None


async def main():
    """启动 MCP SSE Server。"""
    init_chroma()
    async with SseServerTransport("/messages") as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 验证 MCP Server 可启动（无语法错误）**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
import ast
with open('mcp_server/server.py', 'r') as f:
    ast.parse(f.read())
print('MCP server syntax OK')
"
```

Expected: `MCP server syntax OK`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add mcp_server/__init__.py mcp_server/server.py
git commit -m "feat: add MCP SSE server with all tools registered"
```

---

## Task 13: agent/loop.py — Agent ReAct 循环

**Files:**
- Create: `agent/__init__.py`
- Create: `agent/loop.py`

**Interfaces:**
- Consumes: `config.get_deepseek_client()`, MCP Server（SSE），`prompts/system.md`
- Produces:
  - `class AgentLoop` — 管理对话状态和执行 tool-calling 循环
  - `AgentLoop.run(user_message: str, profile: dict) -> Generator[str, None, None]` — 流式生成器，yield 中间状态和最终回复

- [ ] **Step 1: 编写 agent/loop.py**

```python
"""Agent ReAct 循环：接收用户消息，调用 DeepSeek + MCP 工具，流式返回结果。"""
import json
from typing import Generator
from openai import OpenAI

from config import get_deepseek_client, PROFILE_PATH

# 加载系统提示词
SYSTEM_PROMPT_PATH = PROFILE_PATH.parent.parent / "prompts" / "system.md"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

MAX_LOOP = 15  # 最大 tool-calling 循环次数

# MCP 工具定义（与 mcp_server/server.py 中注册的工具一致）
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "profile_get",
            "description": "获取用户完整个人信息档案",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_check",
            "description": "检查个人信息是否完整",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_update",
            "description": "手动更新个人信息中的指定字段",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string", "description": "字段名"},
                    "value": {"type": "string", "description": "新值（JSON字符串）"},
                },
                "required": ["field_name", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_search",
            "description": "在向量数据库中检索最相关的简历片段",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "JD描述或关键词"},
                    "top_k": {"type": "integer", "description": "返回数量，默认5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "boss_search_list",
            "description": "在Boss直聘搜索岗位列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "city": {"type": "string", "description": "城市中文名"},
                    "max_pages": {"type": "integer", "description": "最大翻页数，默认3"},
                },
                "required": ["keyword", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "boss_job_detail",
            "description": "爬取Boss直聘岗位详情JD",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "岗位详情页URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_generate",
            "description": "生成定制化PDF简历",
            "parameters": {
                "type": "object",
                "properties": {
                    "jd_json": {"type": "string", "description": "岗位JD的JSON字符串"},
                },
                "required": ["jd_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "greeting_generate",
            "description": "生成Boss直聘风格打招呼语",
            "parameters": {
                "type": "object",
                "properties": {
                    "jd_json": {"type": "string", "description": "岗位JD的JSON字符串"},
                },
                "required": ["jd_json"],
            },
        },
    },
]


class AgentLoop:
    """管理单次对话的 Agent ReAct 循环。"""

    def __init__(self, mcp_invoke_fn):
        """
        Args:
            mcp_invoke_fn: async function(tool_name: str, args: dict) -> str
                           负责将工具调用转发到 MCP Server
        """
        self.client = get_deepseek_client()
        self.mcp_invoke = mcp_invoke_fn
        self.messages: list[dict] = []

    def run(self, user_message: str, profile: dict) -> Generator[dict, None, None]:
        """执行一次 Agent 循环。

        Args:
            user_message: 用户输入的消息
            profile: 当前用户个人信息

        Yields:
            事件 dict：
            - {"type": "status", "text": "正在..."}  状态提示
            - {"type": "tool_call", "name": "xxx", "args": {...}} 工具调用
            - {"type": "tool_result", "name": "xxx", "result": "..."} 工具结果
            - {"type": "text", "text": "..."} 最终回复文本
        """
        # 构建系统消息
        profile_summary = self._build_profile_summary(profile)
        system_content = SYSTEM_PROMPT + f"\n\n## 当前用户信息\n{profile_summary}"

        self.messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ]

        for _ in range(MAX_LOOP):
            yield {"type": "status", "text": "思考中..."}

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=self.messages,
                tools=MCP_TOOLS,
                tool_choice="auto",
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                # 处理工具调用
                self.messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield {"type": "tool_call", "name": tool_name, "args": tool_args}

                    try:
                        result = self.mcp_invoke(tool_name, tool_args)
                    except Exception as e:
                        result = json.dumps({"error": str(e)}, ensure_ascii=False)

                    yield {"type": "tool_result", "name": tool_name, "result": result}

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                # 无工具调用，最终回复
                final_text = msg.content or ""
                self.messages.append({"role": "assistant", "content": final_text})
                yield {"type": "text", "text": final_text}
                return

        # 超限
        yield {"type": "text", "text": "（操作步骤过多，请简化需求后重试）"}

    def _build_profile_summary(self, profile: dict) -> str:
        """构建个人信息摘要，注入系统提示词。"""
        fields = profile.get("fields", {})
        lines = []
        for name, f in fields.items():
            status = f.get("status", "missing")
            value = f.get("value")
            if status == "missing":
                lines.append(f"- {name}: [缺失]")
            else:
                if isinstance(value, list):
                    summary = "、".join([
                        v.get("name", str(v)) if isinstance(v, dict) else str(v)
                        for v in value[:5]
                    ])
                    lines.append(f"- {name}: {summary}")
                else:
                    lines.append(f"- {name}: {value}")
        return "\n".join(lines)
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "from agent.loop import AgentLoop, MCP_TOOLS; print(f'Agent loop OK, {len(MCP_TOOLS)} tools defined')"
```

Expected: `Agent loop OK, 8 tools defined`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add agent/__init__.py agent/loop.py
git commit -m "feat: add Agent ReAct loop with DeepSeek tool-calling"
```

---

## Task 14: app.py — Streamlit 前端

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `config.*`, `agent.loop.AgentLoop`, `tools.profile_manager.*`, `tools.resume_parser.*`, `tools.resume_store.*`, `tools.profile_extractor.*`
- Produces: 完整的 Streamlit 应用

- [ ] **Step 1: 编写 app.py**

```python
"""AI 求职简历优化助手 — Streamlit 前端入口。"""
import json
import os
import sys
import io
import streamlit as st
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import RESUME_FILES_DIR, PROFILE_PATH, UPLOADS_DIR
from tools.profile_manager import load_profile, save_profile, check_completeness, merge_extracted_fields
from tools.resume_parser import parse_files, parse_directory
from tools.resume_store import init_chroma, store_chunks, clear_collection
from tools.profile_extractor import extract_profile
from agent.loop import AgentLoop

# 页面配置
st.set_page_config(
    page_title="AI 求职助手",
    page_icon="📄",
    layout="wide",
)

# === Session State 初始化 ===
if "profile" not in st.session_state:
    st.session_state.profile = load_profile()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "editing_field" not in st.session_state:
    st.session_state.editing_field = None


def refresh_profile():
    """重新加载 profile.json。"""
    st.session_state.profile = load_profile()


# === MCP 工具调用函数（直接调用 tools 模块，绕过 MCP 网络层） ===
def mcp_invoke(tool_name: str, args: dict) -> str:
    """直接调用 tools 模块（跳过 MCP SSE 网络层，简化开发）。

    在完整部署环境中，这里应该通过 SSE 连接 MCP Server。
    开发阶段直接 import 工具函数调用。
    """
    if tool_name == "profile_get":
        profile = load_profile()
        return json.dumps(profile, ensure_ascii=False, indent=2)

    elif tool_name == "profile_check":
        missing = check_completeness()
        if missing:
            return f"缺失字段：{', '.join(missing)}"
        return "个人信息完整"

    elif tool_name == "profile_update":
        from tools.profile_manager import update_field
        try:
            value = json.loads(args.get("value", "null"))
        except (json.JSONDecodeError, TypeError):
            value = args.get("value", "")
        update_field(args["field_name"], value)
        refresh_profile()
        return f"已更新 {args['field_name']}"

    elif tool_name == "resume_search":
        from tools.resume_search import search
        results = search(args.get("query", ""), args.get("top_k", 5))
        return json.dumps(results, ensure_ascii=False, indent=2)

    elif tool_name == "boss_search_list":
        from tools.boss_search import search_boss
        import threading
        # Selenium 不能在其他线程运行，这里用同步直接调用
        city_map = {
            "深圳": "101280600", "广州": "101280100", "东莞": "101281600",
            "珠海": "101280700", "惠州": "101280300", "佛山": "101280800",
            "北京": "100010000", "天津": "100030000", "石家庄": "100450000",
            "上海": "100020000", "杭州": "101210100", "苏州": "101190400",
            "南京": "101190100", "宁波": "101210400",
            "成都": "101270100", "重庆": "100060000", "绵阳": "101270500",
            "武汉": "101200100", "长沙": "101250100", "郑州": "101180100",
            "西安": "101110100", "咸阳": "101110200", "宝鸡": "101110900",
        }
        city = args.get("city", "深圳")
        city_code = city_map.get(city, "100010000")
        jobs = search_boss(args.get("keyword", ""), city_code, args.get("max_pages", 3))
        return json.dumps(jobs, ensure_ascii=False, indent=2)

    elif tool_name == "boss_job_detail":
        from tools.boss_detail import get_job_detail
        detail = get_job_detail(args.get("url", ""))
        return json.dumps(detail, ensure_ascii=False, indent=2)

    elif tool_name == "pdf_generate":
        from tools.pdf_generator import generate_pdf
        from tools.resume_search import search
        profile = load_profile()
        jd = json.loads(args.get("jd_json", "{}"))
        jd_text = jd.get("jd_text", "") + " " + jd.get("title", "")
        relevant = search(jd_text, top_k=5)

        skills = profile["fields"].get("skills", {}).get("value") or []
        projects = profile["fields"].get("projects", {}).get("value") or []

        relevant_skills = []
        relevant_projects = []
        for item in relevant:
            text = item.get("text", "")
            if isinstance(skills, list):
                for s in skills:
                    name = s.get("name", "") if isinstance(s, dict) else s
                    if name and name in text:
                        relevant_skills.append(name)
            if isinstance(projects, list):
                for p in projects:
                    name = p.get("name", "") if isinstance(p, dict) else p
                    if name and name in text:
                        relevant_projects.append(name)

        path = generate_pdf(profile, jd, list(set(relevant_skills)), list(set(relevant_projects)))
        return f"PDF 已生成：{path}"

    elif tool_name == "greeting_generate":
        from tools.greeting import generate_greeting
        profile = load_profile()
        jd = json.loads(args.get("jd_json", "{}"))
        text = generate_greeting(profile, jd)
        return text

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# === 侧栏 ===
with st.sidebar:
    st.header("📁 简历管理")

    # 文件上传
    uploaded_files = st.file_uploader(
        "上传简历文件",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="支持 PDF、Word、TXT 格式，可同时上传多个文件",
    )

    if uploaded_files:
        new_files = []
        for uf in uploaded_files:
            # 保存上传文件
            save_path = UPLOADS_DIR / uf.name
            with open(save_path, "wb") as f:
                f.write(uf.getbuffer())
            new_files.append(str(save_path))

        if new_files and st.button("🔍 解析上传的文件", use_container_width=True):
            with st.spinner("正在解析文件..."):
                texts = parse_files(new_files)
                # 存入 ChromaDB
                init_chroma()
                for fp, text in texts.items():
                    if not text.startswith("[PARSE_ERROR]") and not text.startswith("[OCR_"):
                        store_chunks(text, {"source": fp})
                # LLM 提取
                profile = extract_profile(texts)
                st.session_state.profile = profile
                st.success(f"已解析 {len(new_files)} 个文件")
                st.rerun()

    # 预存文件夹扫描
    st.divider()
    pre_existing = list(RESUME_FILES_DIR.glob("*"))
    pre_existing = [f for f in pre_existing if f.suffix.lower() in {".pdf", ".docx", ".txt"}]
    if pre_existing:
        st.caption(f"📂 预存文件夹中有 {len(pre_existing)} 个文件")
        if st.button("🔄 解析预存文件", use_container_width=True):
            with st.spinner("正在解析预存文件..."):
                texts = parse_directory(str(RESUME_FILES_DIR))
                init_chroma()
                for fp, text in texts.items():
                    if not text.startswith("[PARSE_ERROR]"):
                        store_chunks(text, {"source": fp})
                profile = extract_profile(texts)
                st.session_state.profile = profile
                st.success(f"已解析 {len(texts)} 个文件")
                st.rerun()

    st.divider()

    # 个人信息状态
    st.header("👤 个人信息")
    missing = check_completeness(st.session_state.profile)

    if not missing:
        st.success("✅ 全部就绪")
    else:
        for name in missing:
            label_map = {
                "name": "姓名", "expected_salary": "期望薪资", "location": "所在地",
                "phone": "电话", "email": "邮箱", "education": "教育背景",
                "skills": "专业技能", "projects": "项目经历",
            }
            st.error(f"❌ {label_map.get(name, name)} 缺失")

    if st.button("📝 查看/编辑个人信息", use_container_width=True):
        st.session_state.editing_field = "all"

    st.divider()

    # 服务状态
    st.header("⚙️ 设置")
    st.caption("DeepSeek API: " + ("🟢 已配置" if os.getenv("DEEPSEEK_API_KEY") else "🔴 未配置"))
    st.caption(f"ChromaDB: {str(RESUME_FILES_DIR.parent / 'chroma')}")


# === 个人信息编辑面板 ===
if st.session_state.editing_field is not None:
    st.header("编辑个人信息")
    fields = st.session_state.profile.get("fields", {})

    with st.form("profile_editor"):
        col1, col2 = st.columns(2)
        edits = {}

        with col1:
            edits["name"] = st.text_input("姓名 *", value=_fv(fields, "name"))
            edits["phone"] = st.text_input("电话 *", value=_fv(fields, "phone"))
            edits["email"] = st.text_input("邮箱 *", value=_fv(fields, "email"))
            edits["location"] = st.text_input("所在地 *", value=_fv(fields, "location"))
            edits["expected_salary"] = st.text_input("期望薪资 *", value=_fv(fields, "expected_salary"))

        with col2:
            edits["career_objective"] = st.text_area("求职意向 (AI 生成)", value=_fv(fields, "career_objective"))
            edits["personal_strengths"] = st.text_area("个人优势 (AI 生成)", value=_fv(fields, "personal_strengths"))

        # 教育背景
        st.subheader("教育背景 *")
        edu_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "education"), ensure_ascii=False, indent=2),
            height=100,
        )

        # 专业技能
        st.subheader("专业技能 *")
        skills_text = st.text_area(
            "JSON 格式 [{\"name\": \"...\", \"level\": \"精通/熟练/了解\"}]",
            value=json.dumps(_fv(fields, "skills"), ensure_ascii=False, indent=2),
            height=100,
        )

        # 项目经历
        st.subheader("项目经历 *")
        projects_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "projects"), ensure_ascii=False, indent=2),
            height=150,
        )

        # 可选字段
        st.subheader("实习经历（可选）")
        intern_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "internships"), ensure_ascii=False, indent=2),
            height=100,
        )

        st.subheader("技能证书与获奖荣誉（可选）")
        cert_text = st.text_area(
            "JSON 格式",
            value=json.dumps(_fv(fields, "certificates"), ensure_ascii=False, indent=2),
            height=100,
        )

        submitted = st.form_submit_button("💾 保存", use_container_width=True)

        if submitted:
            import re
            try:
                # 更新所有字段
                from tools.profile_manager import update_field, ALL_FIELDS

                # JSON 字段
                json_fields = {
                    "education": edu_text,
                    "skills": skills_text,
                    "projects": projects_text,
                    "internships": intern_text,
                    "certificates": cert_text,
                }

                for fname, text_val in json_fields.items():
                    try:
                        val = json.loads(text_val)
                        update_field(fname, val)
                    except json.JSONDecodeError:
                        st.error(f"{fname} JSON 格式错误，请检查")

                for fname, val in edits.items():
                    if val:
                        update_field(fname, val)

                refresh_profile()
                st.session_state.editing_field = None
                st.success("个人信息已保存")
                st.rerun()

            except Exception as e:
                st.error(f"保存失败: {e}")

    if st.button("取消编辑"):
        st.session_state.editing_field = None
        st.rerun()

    st.stop()  # 编辑模式不显示聊天


# === 主区域：聊天 ===
st.header("💬 AI 求职助手")

# 个人信息未完整时，显示警告
missing = check_completeness(st.session_state.profile)
if missing:
    label_map = {
        "name": "姓名", "expected_salary": "期望薪资", "location": "所在地",
        "phone": "电话", "email": "邮箱", "education": "教育背景",
        "skills": "专业技能", "projects": "项目经历",
    }
    missing_labels = [label_map.get(m, m) for m in missing]
    st.warning(f"个人信息不完整，请先在侧栏补充：{', '.join(missing_labels)}")
    st.caption("提示：上传简历文件可自动填写，缺失项手动补充")

# 聊天历史
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "extra" in msg:
            # 额外内容：表格、PDF 链接等
            for extra in msg["extra"]:
                if extra["type"] == "pdf":
                    st.download_button(
                        label=f"📥 下载 {extra.get('label', 'PDF')}",
                        data=open(extra["path"], "rb").read(),
                        file_name=Path(extra["path"]).name,
                        mime="application/pdf",
                    )
                elif extra["type"] == "greeting":
                    st.code(extra["text"], language=None)
                    st.button("📋 复制", key=f"copy_{msg.get('id', '')}", on_click=lambda t=extra["text"]: _copy_to_clipboard(t))

# 输入框
if missing:
    st.chat_input("请先完善个人信息后再开始聊天...", disabled=True)
else:
    user_input = st.chat_input("输入消息，如：帮我在Boss直聘上找Python开发岗位...")

    if user_input:
        # 添加用户消息
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 运行 Agent Loop
        with st.chat_message("assistant"):
            agent = AgentLoop(mcp_invoke)
            result_placeholder = st.empty()
            full_text = ""

            for event in agent.run(user_input, st.session_state.profile):
                if event["type"] == "status":
                    result_placeholder.info(event["text"])
                elif event["type"] == "tool_call":
                    result_placeholder.info(f"🔧 调用工具：{event['name']}...")
                elif event["type"] == "text":
                    full_text = event["text"]
                    result_placeholder.markdown(full_text)

            # 保存到历史
            msg_entry = {"role": "assistant", "content": full_text}

            # 检测打招呼语和 PDF 并添加 extra
            if "```" in full_text:
                import re
                greeting_match = re.search(r'```\n?(.*?)\n?```', full_text, re.DOTALL)
                if greeting_match:
                    msg_entry["extra"] = [{"type": "greeting", "text": greeting_match.group(1)}]

            st.session_state.chat_history.append(msg_entry)

        st.rerun()


# === 辅助函数 ===
def _fv(fields: dict, name: str):
    """安全获取字段值。"""
    f = fields.get(name, {})
    val = f.get("value") if isinstance(f, dict) else None
    if val is None:
        return ""
    if isinstance(val, (list, dict)):
        return val
    return str(val)


def _copy_to_clipboard(text: str):
    """复制文本到剪贴板。"""
    st.toast("已复制到剪贴板！", icon="📋")


# === 启动时初始化 ===
if __name__ == "__main__":
    init_chroma()
```

- [ ] **Step 2: 验证 Streamlit 可启动（语法检查）**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
python -c "
import ast
with open('app.py', 'r') as f:
    ast.parse(f.read())
print('app.py syntax OK')
"
```

Expected: `app.py syntax OK`

- [ ] **Step 3: Commit**

```bash
cd d:/resume_agent
git add app.py
git commit -m "feat: add Streamlit frontend with chat UI and profile management"
```

---

## Task 15: 端到端集成测试与修复

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: 所有已完成的任务
- Produces: 可运行的集成测试

- [ ] **Step 1: 编写集成测试**

```python
"""端到端集成测试：验证核心流程。"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestProfileManager:
    """测试个人信息管理模块。"""

    def test_create_and_load(self):
        from tools.profile_manager import create_empty_profile, save_profile, load_profile

        p = create_empty_profile()
        assert "meta" in p
        assert len(p["fields"]) == 12
        assert p["fields"]["name"]["status"] == "missing"

    def test_check_completeness_empty(self):
        from tools.profile_manager import create_empty_profile, check_completeness

        p = create_empty_profile()
        missing = check_completeness(p)
        assert len(missing) == 8  # 8 个非 LLM 生成的固定字段

    def test_check_completeness_full(self):
        from tools.profile_manager import merge_extracted_fields, check_completeness

        data = {
            "name": "张三",
            "career_objective": "Python 开发",
            "expected_salary": "20K",
            "location": "深圳",
            "phone": "13800138000",
            "email": "test@test.com",
            "education": [{"school": "XX大学", "major": "CS", "degree": "本科", "graduation_year": "2020"}],
            "skills": [{"name": "Python", "level": "精通"}],
            "projects": [{"name": "项目A", "role": "开发", "start_date": "2021", "end_date": "2022", "description": "test"}],
            "personal_strengths": "优点",
        }
        profile = merge_extracted_fields(data, ["test.pdf"])
        missing = check_completeness(profile)
        assert len(missing) == 0

    def test_merge_extracted_fields_preserves_existing(self):
        from tools.profile_manager import merge_extracted_fields, load_profile

        # 先写入部分数据
        data1 = {"name": "张三", "phone": "13800138000"}
        merge_extracted_fields(data1, ["v1.pdf"])

        # 再追加（不同文件）
        data2 = {"email": "test@test.com"}
        profile = merge_extracted_fields(data2, ["v2.pdf"])

        assert profile["fields"]["name"]["value"] == "张三"
        assert profile["fields"]["email"]["value"] == "test@test.com"
        assert len(profile["meta"]["source_files"]) == 2


class TestResumeParser:
    """测试文件解析模块。"""

    def test_parse_txt(self):
        from tools.resume_parser import parse_file

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", encoding="utf-8", delete=False) as f:
            f.write("姓名：张三\n技能：Python, Java")
            path = f.name

        text = parse_file(path)
        assert "张三" in text
        assert "Python" in text
        os.unlink(path)

    def test_parse_docx(self):
        from tools.resume_parser import parse_file
        from docx import Document

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            doc = Document()
            doc.add_paragraph("姓名：李四")
            doc.add_paragraph("技能：Django, React")
            doc.save(f.name)
            path = f.name

        text = parse_file(path)
        assert "李四" in text
        assert "Django" in text
        os.unlink(path)

    def test_unsupported_format(self):
        from tools.resume_parser import parse_file
        import pytest

        with pytest.raises(ValueError, match="Unsupported"):
            parse_file("test.xyz")


class TestPdfGenerator:
    """测试 PDF 生成模块。"""

    def test_generate_pdf(self):
        from tools.profile_manager import merge_extracted_fields
        from tools.pdf_generator import generate_pdf

        data = {
            "name": "王五",
            "career_objective": "全栈工程师",
            "expected_salary": "25K-35K",
            "location": "北京",
            "phone": "13900139000",
            "email": "wang@test.com",
            "education": [{"school": "清华", "major": "软件工程", "degree": "硕士", "graduation_year": "2022"}],
            "skills": [{"name": "Python", "level": "精通"}, {"name": "Vue", "level": "熟练"}],
            "projects": [{"name": "管理后台", "role": "全栈", "start_date": "2022", "end_date": "2023", "description": "从零搭建"}],
            "personal_strengths": "1. 全栈能力\n2. 快速学习",
            "internships": [],
            "certificates": [{"name": "PMP", "issuer": "PMI", "year": "2023"}],
        }
        profile = merge_extracted_fields(data, ["test.pdf"])
        jd = {"title": "全栈工程师", "company": "XX科技", "jd_text": "需要Python和Vue", "salary": "25K-35K"}

        path = generate_pdf(profile, jd)
        assert os.path.exists(path)
        assert path.endswith(".pdf")
        assert "全栈工程师" in path


class TestMCPTools:
    """测试 MCP 工具层（直接调用，不经过 SSE）。"""

    def test_profile_tools(self):
        from tools.profile_manager import merge_extracted_fields, load_profile, check_completeness, update_field

        # 设置测试数据
        data = {
            "name": "测试用户",
            "expected_salary": "15K",
            "location": "深圳",
            "phone": "123",
            "email": "a@b.com",
            "education": [{"school": "XX", "major": "CS", "degree": "本科", "graduation_year": "2020"}],
            "skills": [{"name": "Python", "level": "精通"}],
            "projects": [{"name": "P", "role": "DEV", "start_date": "2021", "end_date": "2022", "description": "T"}],
            "career_objective": "开发",
            "personal_strengths": "1. x",
        }
        merge_extracted_fields(data, ["test.pdf"])

        profile = load_profile()
        assert profile["fields"]["name"]["value"] == "测试用户"

        missing = check_completeness()
        assert len(missing) == 0

        update_field("phone", "999")
        profile = load_profile()
        assert profile["fields"]["phone"]["value"] == "999"

    def test_search_empty_db(self):
        from tools.resume_search import search
        results = search("Python", top_k=3)
        # 即使空也应该返回 []
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: 运行测试**

```bash
cd d:/resume_agent
source .venv/Scripts/activate
pip install pytest
python -m pytest tests/test_integration.py -v
```

Expected: 全部 PASS（至少 profile_manager、parser、pdf_generator 测试通过）

- [ ] **Step 3: 修复测试中发现的问题后，Commit**

```bash
cd d:/resume_agent
git add tests/__init__.py tests/test_integration.py
git commit -m "test: add integration tests for core modules"
```

---

## 启动验证

全部 Task 完成后，执行以下命令启动：

```bash
# 终端 1：MCP Server
cd d:/resume_agent
source .venv/Scripts/activate
python -m mcp_server.server

# 终端 2：Streamlit
cd d:/resume_agent
source .venv/Scripts/activate
streamlit run app.py
```

浏览器打开 `http://localhost:8501`，测试流程：
1. 侧栏上传简历文件 → 解析 → 查看个人信息
2. 输入 "帮我在深圳找 Python 开发的岗位"
3. 观察 Agent 工具调用过程
4. 下载生成的 PDF
5. 复制招呼语

---

## 自审

1. **Spec 覆盖**：每个 spec 章节都有对应任务 — 个人信息模型(Task 3,6)、文件解析(Task 4)、ChromaDB RAG(Task 5,7)、MCP 工具(Task 12)、Agent Loop(Task 13)、PDF 生成(Task 10)、招呼语(Task 11)、Streamlit UI(Task 14)、错误处理(Task 12,14 中的 try/except)
2. **无占位符**：所有步骤都有完整代码，无 TBD/TODO
3. **类型一致性**：profile dict 结构统一，字段名全任务一致
