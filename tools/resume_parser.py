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
