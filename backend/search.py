# search.py
from tavily import TavilyClient
import config

# Initialize safely
tavily_client = None
if config.TAVILY_KEY:
    try:
        tavily_client = TavilyClient(api_key=config.TAVILY_KEY)
    except Exception as e:
        print("Tavily Init Error: " + str(e))

def get_web_context(query, deep_dive=False):
    """
    Fetches live web data to provide context to the AI Brain.
    """
    if not tavily_client:
        return ""
        
    try:
        search_depth = "advanced" if deep_dive else "basic"
        results = tavily_client.search(query=query, search_depth=search_depth, max_results=5)
        
        context = "\n[DYNAMO WEB CONTEXT]:\n"
        for r in results.get('results', []):
            context += "- " + str(r.get('title')) + ": " + str(r.get('content')) + " (Source: " + str(r.get('url')) + ")\n"
        return context
    except Exception as e:
        print("Search Error: " + str(e))
        return ""
