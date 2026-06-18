"""
若茗 PaaS - 文档解析器基类与工厂
Author: ruoming
"""
from __future__ import annotations

import io
import re
import structlog

logger = structlog.get_logger(__name__)


def parse_document(source_type: str, content: bytes, filename: str = "") -> str:
    """
    文档解析工厂函数。
    根据来源类型和文件名自动选择解析器。
    支持：txt / md / pdf / docx / html / url / text
    """
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    # 纯文本类型
    if source_type in ("text",) or ext in ("txt", "md", "markdown", "csv", "log"):
        return _parse_text(content)

    # PDF
    if source_type == "file" and ext == "pdf":
        return _parse_pdf(content)

    # Word
    if source_type == "file" and ext in ("docx", "doc"):
        return _parse_docx(content)

    # HTML
    if source_type in ("url", "html") or ext in ("html", "htm"):
        return _parse_html(content)

    # 默认尝试按 UTF-8 解码
    try:
        text = content.decode("utf-8", errors="replace")
        return text.strip()
    except Exception:
        return ""


def _parse_text(content: bytes) -> str:
    """纯文本解析"""
    try:
        return content.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _parse_pdf(content: bytes) -> str:
    """PDF 解析（依赖 pymupdf 或 pdfminer）"""
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=content, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(p.strip() for p in pages if p.strip())
    except ImportError:
        pass

    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        output = io.StringIO()
        extract_text_to_fp(io.BytesIO(content), output, laparams=LAParams())
        return output.getvalue().strip()
    except ImportError:
        logger.warning("pdf_parser_not_available", note="请安装 pymupdf 或 pdfminer.six")
        return "[PDF 解析失败：请安装 pymupdf 或 pdfminer.six]"


def _parse_docx(content: bytes) -> str:
    """Word 文档解析（依赖 python-docx）"""
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except ImportError:
        logger.warning("docx_parser_not_available", note="请安装 python-docx")
        return "[DOCX 解析失败：请安装 python-docx]"


def _parse_html(content: bytes) -> str:
    """HTML 解析，移除标签（依赖 beautifulsoup4）"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        # 移除脚本和样式
        for tag in soup(["script", "style", "head", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # 清理多余空行
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)
    except ImportError:
        logger.warning("html_parser_not_available", note="请安装 beautifulsoup4")
        # 降级：用正则删除 HTML 标签
        text = re.sub(r"<[^>]+>", " ", content.decode("utf-8", errors="replace"))
        return re.sub(r"\s+", " ", text).strip()
