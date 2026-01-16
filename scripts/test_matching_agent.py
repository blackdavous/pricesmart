
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Load backend env
env_path = backend_path / ".env"
load_dotenv(env_path)

import logging
from app.agents.product_matching import ProductMatchingAgent
from app.mcp_servers.mercadolibre.models import Offer

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')

    print("Testing ProductMatchingAgent Isolation...")
    
    # Check API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment. Testing FALLBACK logic...")
        # return  <-- Commented out to test fallback
    else:
        print(f"✅ Found OPENAI_API_KEY: {api_key[:5]}...")

    try:
        agent = ProductMatchingAgent()
        
        # Test Data (Offers found by scraper previously)
        offers = [
            {"title": "Audífonos Bluetooth Sony WH-CH520 Negro", "price": 899.0, "item_id": "MLM1", "url": "http://example.com/1"},
            {"title": "Sony WH-CH520 Azul - Audífonos Inalámbricos", "price": 950.0, "item_id": "MLM2", "url": "http://example.com/2"},
            {"title": "Funda Estuche Para Sony Wh-ch520", "price": 200.0, "item_id": "MLM3", "url": "http://example.com/3"},
            {"title": "Audífonos Inalámbricos Jbl Tune 510bt", "price": 700.0, "item_id": "MLM4", "url": "http://example.com/4"},
        ]
        
        target = "Audífonos Bluetooth Sony"
        
        print(f"\nTarget: {target}")
        print(f"Input Offers: {len(offers)}")
        
        result = await agent.execute(target, offers)
        
        print("\n--- Matching Result ---")
        print(f"Comparable Count: {result['comparable_count']}")
        print(f"Excluded Count: {result['excluded_count']}")
        
        print("\nClassifications:")
        for c in result['classifications']:
            status = "✅ Comparable" if c['is_comparable'] else "❌ Excluded"
            print(f"  [{c['item_id']}] {c['title']} -> {status} ({c['reason']})")
            
        if result['comparable_count'] >= 2:
            print("\n✅ Matching Logic Verified (Expected >= 2 comparables)")
        else:
            print("\n❌ Matching Logic FAILED (Too strict)")

    except Exception as e:
        print(f"\n❌ Exception during matching: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
