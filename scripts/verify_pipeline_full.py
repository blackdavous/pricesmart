
import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.agents.pricing_pipeline import PricingPipeline

async def run_test():
    print("Starting Pipeline Test...")
    pipeline = PricingPipeline()
    
    # Use the user's problematic query
    product_query = "Bocina 8 Profesional Ideal Para Bafles 8ohm"
    
    print(f"Analyze: {product_query}")
    result = await pipeline.analyze_product(
        product_input=product_query,
        max_offers=5, # Small batch for speed
        cost_price=500.0,
        target_margin=40.0
    )
    
    print("\nPipeline Finished")
    print(f"Errors: {result.get('errors', [])}")
    
    steps = result.get("pipeline_steps", {})
    print(f"Steps Completed: {list(steps.keys())}")
    
    if "matching" in steps:
        m_step = steps["matching"]
        print(f"\nMatching Step Status: {m_step.get('status')}")
        print(f"   Total: {m_step.get('total_offers')}")
        print(f"   Comparable: {m_step.get('comparable')}")
        print(f"   Excluded: {m_step.get('excluded')}")
        
        comps = m_step.get("comparable_offers", [])
        print(f"   Filtered List Size: {len(comps)}")
        for c in comps:
             print(f"     - {c.get('title')} (${c.get('price')})")
    else:
        print("\nMATCHING STEP MISSING! Pipeline likely crashed before completion.")

    if "scraping" in steps:
        s_offers = steps["scraping"].get("offers", [])
        print(f"\nScraped Offers (Raw): {len(s_offers)}")
        # Check fallback
        if "matching" not in steps:
            print("Dashboard would show these raw offers due to fallback.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_test())
