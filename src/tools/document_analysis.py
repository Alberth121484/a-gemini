import httpx
import io
import base64
import structlog
from typing import Optional, Dict, Any
from pathlib import Path

from ..config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class DocumentAnalysisTool:
    """Document analysis for PDF, Excel, Word, and other formats."""
    
    name = "document_analysis"
    description = "Analyzes documents (PDF, Excel, Word, PowerPoint, etc.) and extracts their content."
    
    SUPPORTED_EXTENSIONS = {
        ".pdf": "pdf",
        ".xlsx": "xlsx",
        ".xls": "xls",
        ".docx": "docx",
        ".doc": "doc",
        ".pptx": "pptx",
        ".ppt": "ppt",
        ".csv": "csv",
        ".txt": "text",
        ".rtf": "rtf",
        ".html": "html",
        ".xml": "xml",
        ".json": "json",
        ".ods": "ods",
        ".ics": "ics",
    }
    
    def __init__(self):
        self.convert_api_key = settings.convert_api_key
        self.slack_token = settings.slack_bot_token
    
    async def download_file(self, url: str) -> tuple[bytes, str]:
        """Download file from Slack and detect extension."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {self.slack_token}"},
                follow_redirects=True
            )
            response.raise_for_status()
            
            # Try to get filename from content-disposition or URL
            content_disp = response.headers.get("content-disposition", "")
            if "filename=" in content_disp:
                filename = content_disp.split("filename=")[-1].strip('"\'')
            else:
                filename = url.split("/")[-1].split("?")[0]
            
            return response.content, filename
    
    def get_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        return Path(filename).suffix.lower()
    
    async def extract_pdf(self, content: bytes) -> str:
        """Extract text from PDF."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error("PDF extraction error", error=str(e))
            raise
    
    async def extract_xlsx(self, content: bytes) -> str:
        """Extract data from Excel (xlsx)."""
        try:
            import pandas as pd
            xlsx = pd.ExcelFile(io.BytesIO(content))
            all_data = []
            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)
                all_data.append(f"## Hoja: {sheet_name}\n{df.to_markdown(index=False)}")
            return "\n\n".join(all_data)
        except Exception as e:
            logger.error("Excel extraction error", error=str(e))
            raise
    
    async def extract_xls(self, content: bytes) -> str:
        """Extract data from Excel (xls)."""
        return await self.extract_xlsx(content)
    
    async def extract_docx(self, content: bytes) -> str:
        """Extract text from Word document."""
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            logger.error("Word extraction error", error=str(e))
            raise
    
    async def extract_csv(self, content: bytes) -> str:
        """Extract data from CSV."""
        try:
            import pandas as pd
            df = pd.read_csv(io.BytesIO(content))
            return df.to_markdown(index=False)
        except Exception as e:
            logger.error("CSV extraction error", error=str(e))
            raise
    
    async def extract_text(self, content: bytes) -> str:
        """Extract text from plain text file."""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1")
    
    async def extract_json(self, content: bytes) -> str:
        """Extract and format JSON."""
        import json
        try:
            data = json.loads(content)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("JSON extraction error", error=str(e))
            raise
    
    async def extract_html(self, content: bytes) -> str:
        """Extract text from HTML."""
        try:
            from html.parser import HTMLParser
            
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                
                def handle_data(self, data):
                    text = data.strip()
                    if text:
                        self.text_parts.append(text)
            
            parser = TextExtractor()
            parser.feed(content.decode("utf-8"))
            return " ".join(parser.text_parts)
        except Exception as e:
            logger.error("HTML extraction error", error=str(e))
            raise
    
    async def convert_pptx_to_pdf(self, content: bytes) -> bytes:
        """Convert PowerPoint to PDF using ConvertAPI."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://v2.convertapi.com/convert/pptx/to/pdf",
                    headers={
                        "Authorization": f"Bearer {self.convert_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "Parameters": [
                            {
                                "Name": "File",
                                "FileValue": {
                                    "Name": "document.pptx",
                                    "Data": base64.b64encode(content).decode()
                                }
                            },
                            {"Name": "StoreFile", "Value": True}
                        ]
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                # Download converted PDF
                pdf_url = data["Files"][0]["Url"]
                pdf_response = await client.get(pdf_url)
                return pdf_response.content
        except Exception as e:
            logger.error("PPTX conversion error", error=str(e))
            raise
    
    async def convert_doc_to_pdf(self, content: bytes, from_format: str) -> bytes:
        """Convert Word document to PDF using ConvertAPI."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"https://v2.convertapi.com/convert/{from_format}/to/pdf",
                    headers={
                        "Authorization": f"Bearer {self.convert_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "Parameters": [
                            {
                                "Name": "File",
                                "FileValue": {
                                    "Name": f"document.{from_format}",
                                    "Data": base64.b64encode(content).decode()
                                }
                            },
                            {"Name": "StoreFile", "Value": True}
                        ]
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                pdf_url = data["Files"][0]["Url"]
                pdf_response = await client.get(pdf_url)
                return pdf_response.content
        except Exception as e:
            logger.error(f"{from_format.upper()} conversion error", error=str(e))
            raise
    
    async def execute(self, file_url: str, query: Optional[str] = None) -> str:
        """Analyze a document and extract its content."""
        try:
            # Download file
            content, filename = await self.download_file(file_url)
            ext = self.get_extension(filename)
            
            logger.info("Processing document", filename=filename, extension=ext, size=len(content))
            
            # Extract based on type
            if ext == ".pdf":
                text = await self.extract_pdf(content)
            elif ext == ".xlsx":
                text = await self.extract_xlsx(content)
            elif ext == ".xls":
                text = await self.extract_xls(content)
            elif ext == ".docx":
                text = await self.extract_docx(content)
            elif ext in [".doc"]:
                # Convert old doc format to PDF first
                pdf_content = await self.convert_doc_to_pdf(content, "doc")
                text = await self.extract_pdf(pdf_content)
            elif ext == ".pptx":
                pdf_content = await self.convert_pptx_to_pdf(content)
                text = await self.extract_pdf(pdf_content)
            elif ext == ".csv":
                text = await self.extract_csv(content)
            elif ext in [".txt", ".rtf"]:
                text = await self.extract_text(content)
            elif ext == ".html":
                text = await self.extract_html(content)
            elif ext == ".json":
                text = await self.extract_json(content)
            elif ext == ".xml":
                text = await self.extract_text(content)
            else:
                return f"Formato de archivo no soportado: {ext}"
            
            # Truncate if too long
            max_length = 50000
            if len(text) > max_length:
                text = text[:max_length] + "\n\n[... contenido truncado ...]"
            
            return text
            
        except httpx.HTTPStatusError as e:
            logger.error("Document download error", status=e.response.status_code)
            return f"Error al descargar el documento: {e.response.status_code}"
        except Exception as e:
            logger.error("Document analysis error", error=str(e))
            return f"Error al analizar el documento: {str(e)}"
