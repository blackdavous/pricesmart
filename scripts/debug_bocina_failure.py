
import asyncio
import os
import sys
import re
from typing import List, Dict, Any

# Simplified Debug Script
# No external deps if possible, just logic tests

class MockAgent:
    def _extract_essential_keywords(self, text: str) -> List[str]:
        tokens = text.split()
        keywords = []
        for token in tokens:
             clean = re.sub(r'[^a-zA-Z0-9]', '', token)
             if len(clean) < 2: continue
             
             # Exclude common spec units
             if re.match(r'^\d+(?:ohm|w|v|kw|hp|kg|g|lb|oz|ml|l|m|cm|mm|in|ft|gb|tb|hz|khz|mah)$', clean.lower()):
                 continue
                 
             has_digit = any(c.isdigit() for c in clean)
             is_upper = clean.isupper()
             
             if has_digit or (is_upper and len(clean) >= 3):
                 keywords.append(clean.lower())
        return keywords

    def _extract_specs(self, text: str):
        specs = {"size": set(), "impedance": set()}
        text = text.lower()
        
        def add_matches(category, pattern):
            matches = re.findall(pattern, text)
            for m in matches: specs[category].add(m)

        # Size 
        add_matches("size", r'\b(\d{1,2}(?:\.\d)?)\s?(?:"|in|pulg|pulgadas)\b')
        add_matches("size", r'\b(?:bocina|bafle|subwoofer|parlante|woofer|medio|driver)\s+(\d{1,2})\b')
        
        # Impedance
        add_matches("impedance", r'\b(\d{1,2})\s?ohms?\b')
        add_matches("impedance", r'\b(\d{1,2})ohm\b')
        
        return specs

    def _calculate_token_overlap(self, s1: str, s2: str) -> float:
        def clean_tokens(text):
            tokens = re.findall(r'\b[a-z0-9]{3,}\b', text.lower())
            stop_words = {'para', 'con', 'los', 'las', 'una', 'uno', 'del', 'por', 'que', 'for', 'with', 'the', 'and'}
            return set(t for t in tokens if t not in stop_words)
            
        set1 = clean_tokens(s1)
        set2 = clean_tokens(s2)
        if not set1 or not set2: return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

async def test_logic():
    agent = MockAgent()
    
    target_title = "Bocina 8 Profesional Ideal Para Bafles 8ohm Por Pieza Color Negro"
    ref_price = 500.0
    
    # 1. Test Keyword Extraction
    keywords = agent._extract_essential_keywords(target_title)
    print(f"Keywords: {keywords}")
    
    # 2. Test Spec Extraction
    specs = agent._extract_specs(target_title)
    print(f"Specs: {specs}")
    
    candidate_good = "Bafle Bocina 8 Pulgadas 8 Ohms"
    print(f"\nCandidate: {candidate_good}")
    
    # 3. Test Token Overlap
    overlap = agent._calculate_token_overlap(target_title, candidate_good)
    print(f"Token Overlap Score: {overlap:.4f}")
    if overlap < 0.15:
        print("FAIL: Token Overlap too low (< 0.15)")
    else:
        print("PASS: Token Overlap OK")
        
    # 4. Test Price Safety
    price_good = 450.0
    print(f"\nScanning Price: ${price_good}")
    ratio = price_good / ref_price
    print(f"Price Ratio: {ratio:.2f}")
    if ratio < 0.4: print("FAIL: Too Cheap")
    elif ratio > 3.5: print("FAIL: Too Expensive")
    else: print("PASS: Price OK")

if __name__ == "__main__":
    if sys.platform == "win32":
        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        pass
    asyncio.run(test_logic())
