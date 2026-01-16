
import asyncio
import os
import sys
import numpy as np

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from app.core.config import settings
from langchain_openai import OpenAIEmbeddings

# Mock target and offers from User's context
TARGET = "Bocina 8 Profesional Ideal Para Bafles 8ohm Por Pieza Color Negro"

CANDIDATES = [
    # RELEVANT (Should match)
    "Bocina 8 Profesional Ideal Para Bafles 4ohm Por Pieza Color Negro", # Same but 4ohm
    "Bocina 8 Pulgadas Profesional 8 Ohms", # Ideal match
    
    # IRRELEVANT (Should mismatch logic, but check similarity)
    "Bafle Bocina 15 Pulgadas Pasivo 8 Ohms 3 Vias Megapower Pro", # Different size
    "Bocina 12 Pulgadas Profesional 8 Ohms X Pieza Color Negro",   # Different size
    "Rockford Fosgate Punch Subwoofer 8 4ohms P2d4-8 Negro",       # Subwoofer vs Speaker?
    "32mm 4ohm 3w Reemplazo De De Sonido",                         # Trash
    "Cable para bocina calibre 14"                                 # Trash
]

async def check_similarity():
    # Fetch key safely
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ NO API KEY FOUND. Please set OPENAI_API_KEY.")
        return

    print(f"🔑 API Key found: {api_key[:5]}...")
    
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key
        )
        
        print(f"\n🎯 TARGET: {TARGET}")
        target_vec = await embeddings.aembed_query(TARGET)
        
        print("\n📊 SIMILARITY SCORES:")
        print(f"{'SCORE':<10} | {'CANDIDATE'}")
        print("-" * 60)
        
        for text in CANDIDATES:
            vec = await embeddings.aembed_query(text)
            
            # Cosine Similarity
            similarity = np.dot(target_vec, vec) / (np.linalg.norm(target_vec) * np.linalg.norm(vec))
            
            status = "✅" if similarity >= 0.25 else "❌"
            print(f"{similarity:.4f} {status} | {text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_similarity())
