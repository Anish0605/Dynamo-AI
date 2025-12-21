#search.py
from tavily import TavilyClient
import config

tavily_client = TavilyClient(api_key=config.TAVILY_KEY) if config.TAVILY_KEY else None

def get_web_context(query, deep_dive=False):
    if not tavily_client: return ""
    try:
        search_depth = "advanced" if deep_dive else "basic"
        results = tavily_client.search(query=query, search_depth=search_depth, max_results=5)
        
        context = "\n[RESEARCH DATA]:\n"
        for r in results.get('results', []):
            context += f"- {r['title']}: {r['content']} ({r['url']})\n"
        return context
    except: return ""
