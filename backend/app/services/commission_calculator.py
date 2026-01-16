
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class CostBreakdown:
    selling_price: float
    gross_commission: float
    shipping_cost: float
    taxes_isr: float
    taxes_vat: float
    cost_of_goods: float
    net_profit: float
    net_margin_percent: float
    return_on_investment: float
    breakdown: Dict[str, float]

class CommissionCalculator:
    """
    Calculator for Mercado Libre Mexico fees, shipping, and taxes (2026).
    """
    
    # 2026 Approximate Shipping Rates for Mercado Envíos (Standard)
    # Weight Range (kg) -> Cost (MXN)
    # Based on public landing pages and seller experience
    SHIPPING_RATES_2025 = {
        0.5: 95.0,  # 0 - 0.5 kg
        1.0: 110.0, # 0.5 - 1 kg
        2.0: 135.0, # 1 - 2 kg
        3.0: 155.0, # 2 - 3 kg (Estimated trend)
        5.0: 195.0, # 3 - 5 kg
        10.0: 300.0, # 5 - 10 kg
        15.0: 400.0,
        20.0: 500.0
    }
    
    # Reputation Discounts (for Free Shipping > $299)
    REPUTATION_DISCOUNT = {
        "MercadoLider": 0.50, # 50% discount
        "Green": 0.40,        # 40% discount
        "Yellow": 0.0,        # No discount
        "Orange": 0.0,
        "Red": 0.0,
        "None": 0.0
    }

    @staticmethod
    def calculate_shipping(
        price: float, 
        weight_kg: float = 1.0, 
        reputation: str = "Green",
        listing_type: str = "Clásica"
    ) -> float:
        """
        Calculate shipping cost for the seller.
        Rule: > $299 MXN, Seller pays (with discount). < $299, Buyer pays (Cost = 0 for seller).
        """
        if price < 299:
            return 0.0
            
        # Find rate based on weight
        base_rate = CommissionCalculator.SHIPPING_RATES_2025[0.5] # Min base
        sorted_weights = sorted(CommissionCalculator.SHIPPING_RATES_2025.keys())
        
        for w in sorted_weights:
            if weight_kg <= w:
                base_rate = CommissionCalculator.SHIPPING_RATES_2025[w]
                break
            # If heavier than max in table, use basic linear extrapolation (risky but better than nothing)
            if weight_kg > sorted_weights[-1]:
                extra_kg = weight_kg - sorted_weights[-1]
                base_rate = CommissionCalculator.SHIPPING_RATES_2025[sorted_weights[-1]] + (extra_kg * 25.0)

        # Apply discount
        discount = CommissionCalculator.REPUTATION_DISCOUNT.get(reputation, 0.0)
        
        # New 2025 Logic: Premium listings might have different support, 
        # but usually discount is bound to Reputation + Meli+ level. 
        # We'll stick to Reputation for simplicity.
        
        final_cost = base_rate * (1 - discount)
        return round(final_cost, 2)

    @staticmethod
    def calculate_commission(
        price: float, 
        category_fee_percent: float = 15.0, # Average for Electronics
        listing_type: str = "Clásica"
    ) -> float:
        """
        Calculate selling fee.
        Type Clásica: % Fee
        Type Premium: % Fee + Extra (usually +5%)
        Fixed Cost: +$25 MXN if price < $299
        """
        
        # Premium usually adds ~4-5% over Classic
        effective_percent = category_fee_percent
        if listing_type == "Premium":
            effective_percent += 5.0
            
        variable_fee = price * (effective_percent / 100.0)
        
        fixed_fee = 0.0
        if price < 299:
            fixed_fee = 25.0 # Fixed cost for low value items (2024/25 adjustment)
            
        return round(variable_fee + fixed_fee, 2)

    @staticmethod
    def calculate_taxes(
        price: float,
        is_registered: bool = False # If RFC registered, retention is lower or 0 if uploaded
    ) -> Dict[str, float]:
        """
        Calculate ISR and VAT retention.
        Standard Retention (No RFC or Non-verified):
        VAT: 8% (50% of 16%)
        ISR: 2.5% (approx average of tiered table, or max 5.4% for unverified)
        
        If Registered: ML retains less, but we want to show 'money kept by ML'.
        User specific requirement: ISR 2.5%, VAT 8%.
        """
        # Based on user requirement
        vat_retention = price * 0.08
        isr_retention = price * 0.025
        
        return {
            "vat": round(vat_retention, 2),
            "isr": round(isr_retention, 2)
        }

    @classmethod
    def calculate_profit(
        cls,
        selling_price: float,
        cost_of_goods: float,
        weight_kg: float = 1.0,
        category_fee_percent: float = 15.0,
        reputation: str = "Green",
        listing_type: str = "Clásica"
    ) -> CostBreakdown:
        
        commission = cls.calculate_commission(selling_price, category_fee_percent, listing_type)
        shipping = cls.calculate_shipping(selling_price, weight_kg, reputation, listing_type)
        taxes = cls.calculate_taxes(selling_price)
        
        total_deductions = commission + shipping + taxes["vat"] + taxes["isr"] + cost_of_goods
        net_profit = selling_price - total_deductions
        
        margin_percent = 0.0
        roi_percent = 0.0
        
        if selling_price > 0:
            margin_percent = (net_profit / selling_price) * 100.0
            
        if cost_of_goods > 0:
            roi_percent = (net_profit / cost_of_goods) * 100.0
            
        return CostBreakdown(
            selling_price=selling_price,
            gross_commission=commission,
            shipping_cost=shipping,
            taxes_isr=taxes["isr"],
            taxes_vat=taxes["vat"],
            cost_of_goods=cost_of_goods,
            net_profit=round(net_profit, 2),
            net_margin_percent=round(margin_percent, 2),
            return_on_investment=round(roi_percent, 2),
            breakdown={
                "Precio Venta": selling_price,
                "Comisión ML": -commission,
                "Envío": -shipping,
                "Retención IVA (8%)": -taxes["vat"],
                "Retención ISR (2.5%)": -taxes["isr"],
                "Costo Producto": -cost_of_goods,
                "Utilidad Neta": round(net_profit, 2)
            }
        )
