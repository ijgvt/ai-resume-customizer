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

    使用智谱 file_parser API 进行文档解析。
    """
    client = get_zhipu_client()

    try:
        # 使用智谱 file_parser API 直接解析 PDF
        result = client.file_parser.create(
            file=open(file_path, "rb"),
            file_type="pdf",
            tool_type="zhipu-pro",  # 使用智谱自研解析引擎
        )
        task_id = result.id

        # 轮询等待解析完成
        import time
        max_wait = 60
        elapsed = 0
        while elapsed < max_wait:
            status = client.file_parser.retrieve(task_id)
            if status.status == "success":
                break
            if status.status == "failed":
                raise Exception(f"OCR failed: {status}")
            time.sleep(2)
            elapsed += 2

        # 获取解析结果（纯文本格式）
        content = client.file_parser.content(task_id, format_type="text")
        return content.content if hasattr(content, "content") else str(content)

    except Exception as e:
        return f"[OCR_ERROR] {e}"


def _extract_ocr_text(result) -> str:
    """已废弃，OCR 逻辑已合并到 _parse_pdf_via_ocr。保留以防兼容性引用。"""
    try:
        if hasattr(result, "content"):
            return result.content
        if isinstance(result, dict):
            return result.get("content", "") or str(result)
        return str(result)
    except Exception:
        return str(result)
