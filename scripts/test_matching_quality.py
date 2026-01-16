
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from app.agents.product_matching import ProductMatchingAgent
    from app.mcp_servers.mercadolibre.models import Offer
    from app.core.config import settings
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    sys.exit(1)

# Set dummy API key if not present (for testing flow, though LLM will fail/use fallback)
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-dummy-key"
    print("Warning: Using dummy OpenAI Key. LLM calls will fail or use fallback.")

async def main():
    agent = ProductMatchingAgent()
    
    target_product = "Audífonos Sony WH-1000XM5 Cancelación de Ruido"
    # Expected Price: ~5000-7000 MXN
    
    # Test Cases: A mix of Good, Bad (Accessory), Bad (Different Model), Bad (Cheap trash)
    test_offers = [
        # GOOD
        {"title": "Sony WH-1000XM5 Negro Wireless", "price": 6500.0, "item_id": "MLM1", "url": "http://example.com/1", "image_url": "http://img/1"},
        {"title": "Audífonos Noise Cancelling Sony Wh-1000xm5 Plata", "price": 5999.0, "item_id": "MLM2", "url": "http://example.com/2", "image_url": "http://img/2"},
        
        # BAD: Previous Model
        {"title": "Sony WH-1000XM4 Usado", "price": 3500.0, "item_id": "MLM3", "url": "http://example.com/3", "image_url": "http://img/3"},
        
        # BAD: Accessory (Case)
        {"title": "Estuche Rígido Para Sony Wh-1000xm5", "price": 450.0, "item_id": "MLM4", "url": "http://example.com/4", "image_url": "http://example.com/case.jpg"},
        
        # BAD: Accessory (Spare Part)
        {"title": "Almohadillas Repuesto Sony Wh-1000xm5", "price": 300.0, "item_id": "MLM5", "url": "http://example.com/5", "image_url": "http://example.com/pads.jpg"},
        
        # BAD: Completely different
        {"title": "Audífonos Inalámbricos Diadema P9 (Clon)", "price": 250.0, "item_id": "MLM6", "url": "http://example.com/6", "image_url": "http://example.com/clon.jpg"}
    ]
    
    print(f"--- Testing Matching Agent logic for Target: '{target_product}' ---")
    
    # Run classification
    # We call _classify_single_product individually to see detail or use graph
    # Using internal method for direct inspection
    results = []
    for offer in test_offers:
        print(f"\nTesting: {offer['title']} (${offer['price']})")
        # Target Price is ~6000, so we pass 6000 as reference
        classification = await agent._classify_single_product(target_product, offer, reference_price=6000.0)
        print(f"  Result: {classification.is_comparable} (Conf: {classification.confidence})")
        print(f"  Type: {'Accessory' if classification.is_accessory else 'Bundle' if classification.is_bundle else 'Product'}")
        print(f"  Reason: {classification.reason}")
        results.append(classification)

    print("\n--- Summary ---")
    comparable = [c for c in results if c.is_comparable]
    print(f"Total Comparable Found: {len(comparable)} / {len(test_offers)}")
    for c in comparable:
        print(f" - KEPT: {c.title}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
