
import asyncio
import os
import sys
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.agents.pricing_pipeline import PricingPipeline
from app.core.config import settings

# FORCE API KEY FROM ENV (for CLI script usage)
# Try loading from .env manually if needed, or just set a dummy key to test scraper behavior (LLM will fail but match might run partially)
if not settings.OPENAI_API_KEY:
    import os
    k = os.getenv("OPENAI_API_KEY")
    if k:
        settings.OPENAI_API_KEY = k
    else:
        # Try reading .env manually
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        settings.OPENAI_API_KEY = line.split("=", 1)[1].strip()
                        print("Loaded API Key from .env")
                        break
        except:
             pass

    if not settings.OPENAI_API_KEY:
         print("WARNING: No API KEY found. Setting dummy key to allow initialization (Verification will fail).")
         settings.OPENAI_API_KEY = "sk-dummy-key-for-diagnosis"
         os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-diagnosis"

async def diagnose():
    print("STARTING UNIVERSAL DIAGNOSIS...")
    
    if len(sys.argv) > 1:
        product_query = sys.argv[1]
    else:
        # Default
        product_query = "Termo Yeti Rambler 30oz Original"
        
    ref_price = 150.0 # Simulate User entering a low cost (e.g. generic part price)
    
    print(f"Query: {product_query}")
    print(f"Ref Price: ${ref_price}")
    
    pipeline = PricingPipeline()
    
    # Run analysis
    result = await pipeline.analyze_product(
        product_input=product_query,
        max_offers=10, 
        cost_price=500.0,
        target_margin=30.0
    )
    
    steps = result.get("pipeline_steps", {})
    
    # 1. Check Scraping
    scraping_step = steps.get("scraping") or steps.get("1_scraping")
    if scraping_step:
        raw_offers = scraping_step.get("offers", [])
        print(f"\nSCRAPER FOUND: {len(raw_offers)} raw items.")
        if len(raw_offers) == 0:
            print("CRITICAL FAILURE: Scraper returned 0 items. Check network/selectors.")
            return
    else:
         print("CRITICAL: Scraper step missing (Checked 'scraping' and '1_scraping'). Keys found:", list(steps.keys()))
         return

    # 2. Check Matching Details
    avg_price = 0
    matching_step = steps.get("matching") or steps.get("2_matching")
    if matching_step:
        # Check different structure in legacy vs new
        comparable_count = matching_step.get("comparable") or matching_step.get("comparable_count")
        excluded_count = matching_step.get("excluded") or matching_step.get("excluded_count")
        
        print(f"\nMATCHER RESULTS:")
        print(f"   Comparable: {comparable_count}")
        print(f"   Excluded: {excluded_count}")
        
        # New flow exposes 'comparable_offers', legacy might not?
        # In _analyze_from_description: matching_result returned from matching_agent.execute
        # It logs matching_result["comparable_offers"].
        # But looking at code, strict return of _analyze_from_description logic:
        # result["pipeline_steps"]["2_matching"] = { "status", "total_offers", "comparable_count", "excluded_count" }
        # IT DOES NOT INCLUDE THE LIST OF OFFERS in the step dict!
        
        print("   (Note: Legacy pipeline step does not export list details to 'steps' dict)")
        
        # However, we can infer from Final Recommendation if available
        rec = result.get("final_recommendation")
        if rec:
            print(f"\nSUCCESS! Generated Plan: {rec.get('strategy_name')} at ${rec.get('recommended_price')}")
        else:
            print("\nNO RECOMMENDATION GENERATED (Likely 0 comparables)")


            
    # To debug REJECTION REASONS, we would need to inspect logs or modify code.
    # But let's verify if we even HAVE raw offers first.

if __name__ == "__main__":
    if sys.platform == "win32":
        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        pass
    asyncio.run(diagnose())
