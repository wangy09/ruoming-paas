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

    if source_type in ("text",) or ext in ("txt", "md", "markdown", "csv", "log"):
        return _parse_text(content)

    if source_type == "file" and ext == "pdf":
        return _parse_pdf(content)

    if source_type == "file" and ext in ("docx", "doc"):
        return _parse_docx(content)

    if source_type in ("url", "html") or ext in ("html", "htm"):
        return _parse_html(content)

    try:
        text = content.decode("utf-8", errors="replace")
        return text.strip()
    except Exception:
        return ""


def _parse_text(content: bytes) -> str:
    try:
        return content.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _parse_pdf(content: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text()
            if text and text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        pass

    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        output = io.StringIO()
        extract_text_to_fp(io.BytesIO(content), output, laparams=LAParams())
        text = output.getvalue().strip()
        if not text:
            raise ValueError("pdfminer 返回空文本")
        return text
    except ImportError:
        logger.warning("pdf_parser_not_available", note="请安装 pymupdf 或 pdfminer.six")
        return "[PDF 解析失败：请安装 pymupdf 或 pdfminer.six]"
    except Exception as e:
        logger.error("pdf_parse_failed", error=str(e))
        return "[PDF 解析失败]"


def _parse_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = []
        for para in doc.paragraphs:
            if para.text and para.text.strip():
                paragraphs.append(para.text.strip())
        if not paragraphs:
            return ""
        return "\n".join(paragraphs)
    except ImportError:
        logger.warning("docx_parser_not_available", note="请安装 python-docx")
        return "[DOCX 解析失败：请安装 python-docx]"
    except Exception as e:
        logger.error("docx_parse_failed", error=str(e))
        return "[DOCX 解析失败]"


def _parse_html(content: bytes) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "head", "nav", "footer", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n")]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned
    except ImportError:
        logger.warning("html_parser_not_available", note="请安装 beautifulsoup4")
        text = re.sub(r"<[^>]+>", " ", content.decode("utf-8", errors="replace"))
        return re.sub(r"\s+", " ", text).strip()
    except Exception as e:
        logger.error("html_parse_failed", error=str(e))
        return "[HTML 解析失败]"