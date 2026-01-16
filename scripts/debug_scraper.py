
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import logging
from app.mcp_servers.mercadolibre.scraper import MLWebScraper

# Configure logging
logging.basicConfig(level=logging.ERROR) # Less verbose
logger = logging.getLogger("app.mcp_servers.mercadolibre.scraper")
logger.setLevel(logging.INFO)

async def test_query(scraper, query):
    print(f"\nSearching for: {query}")
    try:
        result = await scraper.search_products(query, max_offers=3)
        print(f"  Strategy: {result.strategy}")
        print(f"  Offers: {len(result.offers)}")
        if result.offers:
            print(f"  Sample: {result.offers[0].title} - ${result.offers[0].price}")
        else:
            print("  ❌ No offers found.")
            # Verify if HTML was fetched
            # We can't easily see it unless we modify the scraper to save it, 
            # but getting 'no_offers' likely means 200 OK but parsing failed.
    except Exception as e:
        print(f"  ❌ Exception: {e}")

async def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("Testing Real Scraper with Multiple Queries...")
    scraper = MLWebScraper()
    
    queries = [
        "audifonos bluetooth sony", # The one that worked
        "iphone 15",                # Likely Grid view
        "zapatillas nike",          # Category heavy
        "silla de oficina"          # Generic
    ]
    
    for q in queries:
        await test_query(scraper, q)
        await asyncio.sleep(2) # Polite delay

if __name__ == "__main__":
    asyncio.run(main())
