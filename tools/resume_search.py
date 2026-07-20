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
