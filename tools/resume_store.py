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

    ids = [f"chunk_{collection.count() + i}" for i in range(n)]
    add_kwargs = dict(ids=ids, documents=chunks, embeddings=embeddings)
    if metadata:
        add_kwargs["metadatas"] = [metadata for _ in range(n)]

    collection.add(**add_kwargs)
    return n


def clear_collection() -> None:
    """清空 collection 中的所有数据。"""
    collection = get_collection()
    ids = collection.get()["ids"]
    if ids:
        collection.delete(ids=ids)
