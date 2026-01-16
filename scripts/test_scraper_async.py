import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.mcp_servers.mercadolibre.scraper import MLWebScraper

async def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("Testing MLWebScraper (Async)...")
    scraper = MLWebScraper()
    
    # Test 1: Search
    term = "audifonos bluetooth"
    print(f"Searching for: {term}")
    result = await scraper.search_products(term, max_offers=3)
    
    print(f"Status: {result.strategy}")
    print(f"Found: {len(result.offers)} offers")
    for offer in result.offers:
        print(f" - {offer.title} (${offer.price})")
        
    # Test 2: Details (if any offer found)
    if result.offers:
        url = result.offers[0].url
        print(f"\nExtracting details from: {url}")
        details = await scraper.extract_product_details(url)
        if details:
            print(f"Title: {details.title}")
            print(f"Attributes: {len(details.attributes)} found")
        else:
            print("Failed to extract details")

if __name__ == "__main__":
    asyncio.run(main())
