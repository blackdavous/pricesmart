
from typing import Dict, Set
import re

def _extract_specs(text: str) -> Dict[str, set]:
    """Extract explicit specifications like size, power, capacity, etc."""
    specs = {
        "size": set(),      # Inches, cm
        "power": set(),     # Watts
        "capacity": set(),  # Liters, ml
        "storage": set(),   # GB, TB
        "voltage": set(),   # V, Volts
        "weight": set(),    # kg, lb
        "impedance": set()  # Ohms
    }
    text = text.lower()
    
    # Regex Helpers
    def add_matches(category, pattern):
        matches = re.findall(pattern, text)
        for m in matches:
            specs[category].add(m)

    # 1. Size (Inches/Pulgadas) - e.g. 8", 15 in
    add_matches("size", r'\b(\d{1,2}(?:\.\d)?)\s?(?:"|in|pulg|pulgadas)\b')
    
    # --- PROPOSED ENHANCEMENT: Implicit Audio Sizes ---
    # Look for "Bocina 8", "Bafle 15", "Subwoofer 12"
    implicit_audio_pattern = r'\b(?:bocina|bafle|subwoofer|parlante|woofer)\s+(\d{1,2})\b'
    add_matches("size", implicit_audio_pattern)
    
    # 2. Power (Watts) - e.g. 500W, 1000 Watts
    add_matches("power", r'\b(\d{2,5})\s?(?:w|watts|watt)\b')
    
    # 3. Capacity (Liters) - e.g. 5L, 20 litros
    add_matches("capacity", r'\b(\d{1,3})\s?(?:l|lt|litros|liter)\b')
    
    # 4. Storage (GB/TB) - e.g. 256GB, 1TB
    add_matches("storage", r'\b(\d{1,4})\s?(?:gb|tb|gigas)\b')
    
    # 5. Voltage (Volts) - e.g. 12V, 110V
    add_matches("voltage", r'\b(\d{1,3})\s?(?:v|volts|volt)\b')
    
    # 6. Impedance (Ohms) - e.g. 4 ohm, 8ohms
    add_matches("impedance", r'\b(\d{1,2})\s?(?:ohm|ohms|Ω)\b')
    
    return specs

# Test Cases from USER
target_title = "Bocina 8 Profesional Ideal Para Bafles 8ohm Por Pieza Color Negro"

competitors = [
    "Bafle Bocina 15 Pulgadas Pasivo 8 Ohms 3 Vias Megapower Pro", # Should REJECT (size 15 != 8)
    "Bocina 12 Pulgadas Profesional 8 Ohms X Pieza Color Negro",   # Should REJECT (size 12 != 8)
    "32mm 4ohm 3w Reemplazo De De Sonido De Graves De Graves De",  # Should REJECT (impedance 4 != 8, size fail maybe)
    "Parlantes Jvc 260w 5 Pulgadas (13cm) 4ohm Para Carro Negro",  # Should REJECT (size 5 != 8, impedance 4 != 8)
    "Bocina 15 Pulgadas 300w Rms Megapower Pa 15",                 # Should REJECT (size 15 != 8)
    "Bocina 8 Profesional Ideal Para Bafles 4ohm Por Pieza Color Negro" # Should REJECT (impedance 4 != 8)
]

print(f"TARGET: {target_title}")
t_specs = _extract_specs(target_title)
print(f"EXTRACTED TARGET SPECS: {t_specs}")
print("-" * 50)

for comp in competitors:
    c_specs = _extract_specs(comp)
    print(f"COMP: {comp}")
    print(f"SPECS: {c_specs}")
    
    # Simulate Conflict Logic
    conflict = False
    reasons = []
    
    for category, t_values in t_specs.items():
        if not t_values: continue
        o_values = c_specs[category]
        if not o_values: continue
        
        # Intersection?
        overlap = t_values.intersection(o_values)
        if not overlap:
            conflict = True
            reasons.append(f"{category} mismatch ({t_values} vs {o_values})")
    
    if conflict:
        print(f"❌ REJECTED: {', '.join(reasons)}")
    else:
        print(f"✅ ACCEPTED (No hard conflict)")
    print("")
