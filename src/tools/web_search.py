import httpx
import structlog
from typing import Optional, List, Dict, Any

from ..config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class WebSearchTool:
    """Web search using Tavily API with result synthesis."""
    
    name = "web_search"
    description = "Searches the web for information. Use when you don't have up-to-date information or need to look something up."
    
    def __init__(self):
        self.api_key = settings.tavily_api_key
        self.base_url = "https://api.tavily.com/search"
    
    async def execute(self, query: str, max_results: int = 5) -> str:
        """Execute web search and return synthesized results."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": max_results,
                        "include_answer": True,
                        "include_raw_content": False,
                        "include_images": False,
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            # Return the answer directly if available (Tavily already synthesizes)
            if data.get("answer"):
                return data["answer"]
            
            # Otherwise, format the results
            results = data.get("results", [])
            if not results:
                return "No se encontraron resultados para esta búsqueda."
            
            formatted = []
            for i, result in enumerate(results[:max_results], 1):
                title = result.get("title", "Sin título")
                content = result.get("content", "")[:500]
                url = result.get("url", "")
                formatted.append(f"{i}. **{title}**\n{content}\nFuente: {url}")
            
            return "\n\n".join(formatted)
            
        except httpx.TimeoutException:
            logger.error("Tavily API timeout", query=query)
            return "Error: La búsqueda tardó demasiado tiempo."
        except httpx.HTTPStatusError as e:
            logger.error("Tavily API error", status=e.response.status_code, query=query)
            return f"Error en la búsqueda web: {e.response.status_code}"
        except Exception as e:
            logger.error("Web search error", error=str(e), query=query)
            return f"Error en la búsqueda: {str(e)}"
