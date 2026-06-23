"""
Web Search Tool - uses Serper.dev API.
Inspired by Onyx (tools/tool_implementations/web_search/)
"""
import logging
from typing import Any, Dict, List
import httpx

from .base import BaseTool, ToolCategory, ToolScope, ToolResult, ToolContext
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using Serper.dev API (2500 free searches/month)."""

    name = "web_search"
    display_name = "بحث في الويب"
    description = "ابحث في الويب للحصول على معلومات حديثة. استخدم هذا للأخبار، الطقس، الأسعار، أو أي معلومات قد لا تكون في بياناتك."
    category = ToolCategory.SEARCH
    scope = ToolScope.ALL

    timeout_seconds = 15

    SERPER_API_URL = "https://google.serper.dev"

    def get_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "استعلام البحث (كلمات البحث)",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "عدد النتائج المطلوبة (افتراضي 5، حد أقصى 10)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        query = arguments.get("query", "").strip()
        num_results = min(arguments.get("num_results", 5), 10)

        if not query:
            return ToolResult(
                success=False,
                output="",
                error="query is required",
            )

        if not settings.SERPER_API_KEY:
            return ToolResult(
                success=False,
                output="",
                error="Serper API key not configured",
            )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.SERPER_API_URL}/search",
                    headers={
                        "X-API-KEY": settings.SERPER_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "q": query,
                        "num": num_results,
                        "gl": "sa",  # Saudi Arabia region
                        "hl": "ar",  # Arabic language
                    },
                )
                response.raise_for_status()
                data = response.json()

            # Format results
            organic = data.get("organic", [])
            knowledge_graph = data.get("knowledgeGraph", {})
            answer_box = data.get("answerBox", {})

            citations = []
            output_parts = []

            # Add knowledge graph if available
            if knowledge_graph:
                title = knowledge_graph.get("title", "")
                description = knowledge_graph.get("description", "")
                if description:
                    output_parts.append(f"## {title}\n{description}\n")
                    citations.append({
                        "title": title,
                        "url": knowledge_graph.get("website", ""),
                        "snippet": description[:200],
                        "source": "knowledge_graph",
                    })

            # Add answer box if available
            if answer_box:
                answer_text = answer_box.get("answer") or answer_box.get("snippet") or ""
                if answer_text:
                    output_parts.append(f"**إجابة سريعة:** {answer_text}\n")

            # Add organic results
            for i, result in enumerate(organic[:num_results], 1):
                title = result.get("title", "")
                link = result.get("link", "")
                snippet = result.get("snippet", "")
                source = result.get("source", "")

                output_parts.append(f"{i}. **{title}**")
                if source:
                    output_parts[-1] += f" ({source})"
                output_parts.append(f"   {snippet}")
                output_parts.append(f"   الرابط: {link}\n")

                citations.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "source": source or "web",
                })

            output = "\n".join(output_parts) if output_parts else "لم يتم العثور على نتائج."

            return ToolResult(
                success=True,
                output=output,
                data={
                    "query": query,
                    "total_results": len(organic),
                    "citations_count": len(citations),
                },
                citations=citations,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Serper API error: {e.response.status_code} - {e.response.text[:200]}")
            return ToolResult(
                success=False,
                output="",
                error=f"Search API error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"Web search failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


class WebFetchTool(BaseTool):
    """Fetch and parse content from a URL."""

    name = "web_fetch"
    display_name = "جلب محتوى ويب"
    description = "اجلب واقرأ محتوى صفحة ويب من رابط محدد. مفيد للحصول على تفاصيل من مقال أو صفحة."
    category = ToolCategory.WEB
    scope = ToolScope.ALL

    timeout_seconds = 20

    def get_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "الرابط الكامل للصفحة (URL)",
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "أقصى طول للمحتوى بالأحرف (افتراضي 5000)",
                            "default": 5000,
                        },
                    },
                    "required": ["url"],
                },
            },
        }

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        url = arguments.get("url", "").strip()
        max_length = arguments.get("max_length", 5000)

        if not url:
            return ToolResult(success=False, output="", error="url is required")

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return ToolResult(
                success=False,
                output="",
                error="URL must start with http:// or https://",
            )

        # SSRF protection - block internal IPs
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0") or hostname.startswith("10.") or hostname.startswith("192.168."):
            return ToolResult(
                success=False,
                output="",
                error="Access to internal URLs is blocked",
            )

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; AiNorX/1.0; +https://ai-norx.com)",
                    },
                )
                response.raise_for_status()
                html = response.text

            # Extract text content (basic HTML parsing)
            import re
            # Remove script and style tags
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", html)
            # Clean whitespace
            text = re.sub(r"\s+", " ", text).strip()
            # Decode HTML entities
            import html as html_module
            text = html_module.unescape(text)

            # Truncate
            if len(text) > max_length:
                text = text[:max_length] + "..."

            # Get title
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else parsed.hostname

            return ToolResult(
                success=True,
                output=f"**{title}**\n\n{text}",
                data={
                    "url": url,
                    "title": title,
                    "content_length": len(text),
                    "status_code": response.status_code,
                },
                citations=[{
                    "title": title,
                    "url": url,
                    "snippet": text[:200],
                    "source": "web_fetch",
                }],
            )

        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP error: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"Web fetch failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )
