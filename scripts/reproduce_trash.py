
import asyncio
import os
from app.agents.product_matching import ProductMatchingAgent

# Mock offers based on user screenshot
TRASH_OFFERS = [
    {
        "title": "Bocina Bluetooth Búho Portátil Impermeable Sonido Potente",
        "price": 288.0,
        "item_id": "MLM1",
        "permalink": "https://..."
    },
    {
        "title": "Hapermein Micrófono Karaoke Inalámbrico Color Fucsia con Bocina",
        "price": 199.0,
        "item_id": "MLM2",
        "permalink": "https://..."
    },
    {
        "title": "Bocina Portátil Vorago KSP-303 - Bafle Karaoke 10W",
        "price": 761.0,
        "item_id": "MLM3",
        "permalink": "https://..."
    }
]

# Set dummy key to force agent initialization
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-testing"
    print("Set dummy API key for testing")

TARGET_PRODUCT = "Bocina 8 Profesional Ideal Para Bafles 8ohm Por Pieza Color Negro"

async def test_trash_matches():
    print(f"--- TESTING TRASH MATCHES ---")
    print(f"Target: {TARGET_PRODUCT}")
    
    agent = ProductMatchingAgent()
    
    # Force loading of API key if available, else it will use fallback
    # We want to see WHY it matches.
    
    results = await agent.execute(TARGET_PRODUCT, TRASH_OFFERS, 499.0)
    
    print(f"\nComparable Count: {len(results['comparable_offers'])}")
    print(f"Excluded Count: {results['excluded_count']}")
    
    for offer in results['comparable_offers']:
        print(f"\n[FAILURE] False Positive Found: {offer['title']}")
        # We can't easily see 'reason' here because clean_offers returns list of dicts without reason
        # But we can inspect the agent internals if we ran _classify_single_product individually.

    print("\n--- DETAILED DIAGNOSIS ---")
    for offer in TRASH_OFFERS:
        # Run internal classification to see the logic
        classification = await agent._classify_single_product(
            target=TARGET_PRODUCT,
            offer=offer,
            reference_price=499.0
        )
        print(f"\nProduct: {offer['title']}")
        print(f"Result: {'MATCH' if classification.is_comparable else 'EXCLUDED'}")
        print(f"Confidence: {classification.confidence}")
        print(f"Reason: {classification.reason}")

if __name__ == "__main__":
    # Add backend to path using pathlib for cross-platform safety
    from pathlib import Path
    import sys
    
    # script is in g:/.../scripts/
    # backend is in g:/.../backend/
    backend_path = Path(__file__).parent.parent / "backend"
    
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
        
    print(f"Added to path: {backend_path}")
    
    try:
        from dotenv import load_dotenv
        load_dotenv(backend_path / ".env")
    except:
        pass

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(test_trash_matches())
