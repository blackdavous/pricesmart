"""
Pricing Intelligence Agent - LangGraph implementation.

This agent generates optimal pricing recommendations:
1. Analyzes competitor price distributions
2. Calculates target percentiles
3. Considers profit margins and market position
"""
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import numpy as np
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.core.monitoring import track_agent_execution
from app.mcp_servers.analytics import generate_recommendation_tool, calculate_stats_tool

logger = get_logger(__name__)


class PriceStatistics(BaseModel):
    """Statistical analysis of competitor prices."""
    min_price: float
    max_price: float
    mean_price: float
    median_price: float
    p25: float  # 25th percentile
    p75: float  # 75th percentile
    std_dev: float
    sample_size: int


class PricingRecommendation(BaseModel):
    """Pricing recommendation with reasoning."""
    recommended_price: float
    confidence: str = Field(description="low, medium, high")
    target_percentile: float
    expected_margin_percent: float
    reasoning: str
    alternative_prices: List[float] = Field(default_factory=list)
    market_position: str = Field(description="premium, competitive, budget")
    viability: Optional[Dict[str, Any]] = None


class PricingIntelligenceState(TypedDict):
    """State for pricing intelligence agent."""
    product_id: str
    product_name: str
    cost_price: float
    current_price: Optional[float]
    competitor_prices: List[float]
    price_statistics: Optional[PriceStatistics]
    recommendation: Optional[PricingRecommendation]
    target_margin_percent: float
    target_percentile: float


class PricingIntelligenceAgent:
    """
    LangGraph agent for intelligent pricing recommendations.
    
    Workflow:
    1. calculate_statistics: Analyze price distribution
    2. determine_position: Assess market positioning
    3. generate_recommendation: Create pricing strategy
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_MINI,
            temperature=0.2,
            api_key=settings.OPENAI_API_KEY
        )
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(PricingIntelligenceState)
        
        workflow.add_node("calculate_statistics", self.calculate_statistics)
        workflow.add_node("determine_position", self.determine_position)
        workflow.add_node("generate_recommendation", self.generate_recommendation)
        
        workflow.set_entry_point("calculate_statistics")
        workflow.add_edge("calculate_statistics", "determine_position")
        workflow.add_edge("determine_position", "generate_recommendation")
        workflow.add_edge("generate_recommendation", END)
        
        return workflow.compile()
    
    @track_agent_execution("pricing_intelligence_calculate_statistics")
    async def calculate_statistics(
        self, 
        state: PricingIntelligenceState
    ) -> PricingIntelligenceState:
        """Calculate statistical measures from competitor prices using MCP Analytics."""
        logger.info(
            "Calculating price statistics",
            product=state["product_name"],
            sample_size=len(state["competitor_prices"])
        )
        
        if len(state["competitor_prices"]) == 0:
            logger.warning("No competitor prices available")
            state["price_statistics"] = None
            return state
        
        try:
            # Use MCP calculate_stats_tool
            stats_result = await calculate_stats_tool(state["competitor_prices"])
            
            if stats_result.get("success"):
                stats = PriceStatistics(
                    min_price=stats_result["min"],
                    max_price=stats_result["max"],
                    mean_price=stats_result["mean"],
                    median_price=stats_result["median"],
                    p25=stats_result["q1"],
                    p75=stats_result["q3"],
                    std_dev=stats_result["std_dev"],
                    sample_size=stats_result["sample_size"]
                )
                
                state["price_statistics"] = stats
                
                logger.info(
                    "Statistics calculated via MCP",
                    median=stats.median_price,
                    mean=stats.mean_price,
                    range=(stats.min_price, stats.max_price)
                )
            else:
                logger.error("Stats calculation failed", error=stats_result.get("error"))
                state["price_statistics"] = None
                
        except Exception as e:
            logger.error("Stats calculation exception", error=str(e))
            state["price_statistics"] = None
        
        return state
    
    @track_agent_execution("pricing_intelligence_determine_position")
    async def determine_position(
        self, 
        state: PricingIntelligenceState
    ) -> PricingIntelligenceState:
        """Determine optimal market position based on cost and competition."""
        logger.info("Determining market position")
        
        stats = state.get("price_statistics")
        if not stats:
            return state
        
        cost = state["cost_price"]
        target_margin = state["target_margin_percent"]
        
        # Calculate minimum viable price with target margin
        min_viable_price = cost * (1 + target_margin / 100)
        
        # Determine if we can be competitive with desired margin
        if min_viable_price <= stats.p25:
            position = "budget"
            target_percentile = 25.0
        elif min_viable_price <= stats.median_price:
            position = "competitive"
            target_percentile = 50.0
        else:
            position = "premium"
            target_percentile = 75.0
        
        # Store in state
        state["target_percentile"] = target_percentile
        
        logger.info(
            "Market position determined",
            position=position,
            target_percentile=target_percentile,
            min_viable_price=min_viable_price
        )
        
        return state
    
    @track_agent_execution("pricing_intelligence_generate_recommendation")
    async def generate_recommendation(
        self, 
        state: PricingIntelligenceState
    ) -> PricingIntelligenceState:
        """Generate final pricing recommendation using MCP Analytics."""
        logger.info("Generating pricing recommendation")
        
        if not state.get("price_statistics"):
            logger.warning("No statistics available for recommendation")
            state["recommendation"] = None
            return state
        
        try:
            # Use MCP generate_recommendation_tool
            rec_result = await generate_recommendation_tool(
                cost_price=state["cost_price"],
                competitor_prices=state["competitor_prices"],
                target_margin_percent=state.get("target_margin_percent", 30.0),
                target_percentile=state.get("target_percentile"),
                current_price=state.get("current_price")
            )
            
            if rec_result.get("success"):
                recommendation = PricingRecommendation(
                    recommended_price=rec_result["recommended_price"],
                    confidence=rec_result["confidence"],
                    target_percentile=rec_result["target_percentile"],
                    expected_margin_percent=rec_result["margin_percent"],
                    reasoning=rec_result["reasoning"],
                    alternative_prices=rec_result.get("alternatives", []),
                    market_position=rec_result["market_position"]
                )
                
                # --- CALCULATE VIABILITY SCORE ---
                # MCP tool doesn't do this yet, so we do it here in the agent
                try:
                    # Calculate spread for stability
                    stats = state.get("price_statistics")
                    if stats:
                        iqr = stats.p75 - stats.p25
                        spread_ratio = iqr / stats.median_price if stats.median_price > 0 else 0
                        competitor_count = len(state.get("competitor_prices", []))
                        
                        viability = self._calculate_viability_score(
                            margin_percent=recommendation.expected_margin_percent / 100.0, # convert 20.0 to 0.2
                            competitor_count=competitor_count,
                            spread_ratio=spread_ratio,
                            price_position_percent=0.5
                        )
                        recommendation.viability = viability
                except Exception as e:
                    logger.error(f"Failed to calculate viability in agent: {e}")
                
                state["recommendation"] = recommendation
                
                logger.info(
                    "Recommendation generated via MCP",
                    price=recommendation.recommended_price,
                    margin=recommendation.expected_margin_percent,
                    position=recommendation.market_position
                )
            else:
                logger.error("Recommendation generation failed", error=rec_result.get("error"))
                state["recommendation"] = None
                
        except Exception as e:
            logger.error("Recommendation generation exception", error=str(e))
            state["recommendation"] = None
        
        return state
    
    async def run(
        self,
        product_id: str,
        product_name: str,
        cost_price: float,
        competitor_prices: List[float],
        current_price: Optional[float] = None,
        target_margin_percent: float = 30.0
    ) -> PricingIntelligenceState:
        """
        Execute the pricing intelligence workflow.
        
        Args:
            product_id: Product identifier
            product_name: Product name
            cost_price: Product cost
            competitor_prices: List of competitor prices
            current_price: Current selling price (optional)
            target_margin_percent: Target profit margin
            
        Returns:
            Final state with pricing recommendation
        """
        initial_state: PricingIntelligenceState = {
            "product_id": product_id,
            "product_name": product_name,
            "cost_price": cost_price,
            "current_price": current_price,
            "competitor_prices": competitor_prices,
            "price_statistics": None,
            "recommendation": None,
            "target_margin_percent": target_margin_percent,
            "target_percentile": 50.0  # Will be auto-determined
        }
        
        logger.info(
            "Starting pricing intelligence workflow",
            product=product_name,
            competitors=len(competitor_prices)
        )
        
        final_state = await self.graph.ainvoke(initial_state)
        
        logger.info(
            "Pricing intelligence completed",
            recommended_price=final_state.get("recommendation").recommended_price if final_state.get("recommendation") else None
        )
        
        return final_state
    
    async def execute(
        self,
        target_product: str,
        statistics: Dict[str, Any],
        comparable_count: int,
        cost_price: float = 0,
        target_margin: float = 0.20
    ) -> Dict[str, Any]:
        """
        Execute pricing recommendation from market statistics.
        
        Wrapper method for new pipeline architecture.
        
        Args:
            target_product: Product description
            statistics: Market statistics from stats module
            comparable_count: Number of comparable products
            
        Returns:
            Dict with recommendation and metadata
        """
        logger.info(
            "Executing PricingIntelligenceAgent (new architecture)",
            product=target_product,
            comparable_count=comparable_count
        )
        
        # Extract prices from statistics
        overall = statistics.get("overall", {})
        clean_stats = overall.get("stats_clean", overall.get("stats_all", {}))
        
        median = clean_stats.get("median", 0)
        mean = clean_stats.get("mean", 0)
        q1 = clean_stats.get("q1", median * 0.85 if median else 0)
        q3 = clean_stats.get("q3", median * 1.15 if median else 0)
        min_price = clean_stats.get("min", 0)
        max_price = clean_stats.get("max", 0)
        
        # Determine strategy based on market spread
        spread = q3 - q1 if (q1 and q3) else 0
        spread_ratio = spread / median if median > 0 else 0
        
        if spread_ratio < 0.2:
            strategy = "competitive"
            recommended_price = median
            confidence = 0.85
            reasoning = f"Mercado competitivo con poca variación de precios (IQR: ${spread:,.2f}). Precio recomendado cercano a la mediana de ${median:,.2f} MXN."
        elif spread_ratio > 0.5:
            strategy = "value"
            recommended_price = q1 * 1.05  # 5% arriba del Q1
            confidence = 0.70
            reasoning = f"Mercado con amplia variación de precios (IQR: ${spread:,.2f}). Estrategia de valor posicionándose cerca del Q1 (${q1:,.2f} MXN)."
        else:
            strategy = "competitive"
            recommended_price = median
            confidence = 0.80
            reasoning = f"Mercado moderadamente competitivo. Precio recomendado en la mediana de ${median:,.2f} MXN con {comparable_count} productos comparables."
        
        # Cost-based adjustment
        if cost_price > 0:
            min_margin_price = cost_price * (1 + target_margin)
            if recommended_price < min_margin_price:
                recommended_price = min_margin_price
                strategy = "margin_protection"
                confidence = 0.90
                reasoning = f"Precio ajustado a ${recommended_price:,.2f} para garantizar margen objetivo del {target_margin*100:.0f}% (Costo: ${cost_price:,.2f}). Mercado: ${median:,.2f}."
            else:
                current_margin = (recommended_price - cost_price) / cost_price
                reasoning += f" Margen proyectado: {current_margin*100:.1f}%."
        
        # Calculate market position
        if q1 and q3 and q3 > q1:
            position_pct = ((recommended_price - q1) / (q3 - q1) * 100)
            market_position = f"Positioned at {position_pct:.0f}% within the interquartile range"
        else:
            market_position = "Standard market position"
        
        # Alternative scenarios
        alternatives = {
            "aggressive": round(q1 * 0.95, 2) if q1 else recommended_price * 0.90,
            "conservative": round(median, 2) if median else recommended_price,
            "premium": round(q3 * 0.95, 2) if q3 else recommended_price * 1.15
        }
        
        # Risk factors
        risk_factors = []
        outliers_removed = overall.get("outliers_removed", 0)
        
        if outliers_removed > 3:
            risk_factors.append("⚠️ Mercado con precios atípicos detectados (outliers removidos)")
        else:
            risk_factors.append("✅ Datos de mercado estables")
        
        if comparable_count < 5:
            risk_factors.append("⚠️ Muestra pequeña de productos comparables")
        
        risk_factors.extend([
            "Considerar tendencias estacionales",
            "Monitorear cambios de precios de competidores"
        ])
        
        recommendation = {
            "recommended_price": round(recommended_price, 2),
            "confidence": confidence,
            "strategy": strategy,
            "reasoning": reasoning,
            "market_position": market_position,
            "risk_factors": risk_factors,
            "alternative_prices": alternatives
        }

        # --- VIABILITY SCORE CALCULATION ---
        current_margin_percent = 0.0
        if cost_price > 0:
            current_margin_percent = (recommended_price - cost_price) / recommended_price

        viability = self._calculate_viability_score(
            margin_percent=current_margin_percent,
            competitor_count=comparable_count,
            spread_ratio=spread_ratio,
            price_position_percent=0.5 # Default middle, could be refined
        )
        recommendation["viability"] = viability
        
        return {
            "target_product": target_product,
            "recommendation": recommendation,
            "errors": [],
            "success": True
        }

    def _calculate_viability_score(
        self, 
        margin_percent: float, 
        competitor_count: int, 
        spread_ratio: float,
        price_position_percent: float
    ) -> Dict[str, Any]:
        """
        Calculate a 0-100 viability score for the product.
        
        Weights:
        - Margin (40%): Critical for business survival.
        - Competition (30%): Lower is better.
        - Stability (10%): Lower spread is better (predictable).
        - Position (20%): Can we compete?
        """
        score = 0
        breakdown = []
        
        # 1. MARGIN SCORE (40 pts)
        # Target: >30% margin is great (100%), <10% is bad (0%)
        margin_score = 0
        if margin_percent >= 0.30:
            margin_score = 100
        elif margin_percent <= 0.10:
            margin_score = 0
        else:
            # Linear interpolation between 0.10 and 0.30
            margin_score = ((margin_percent - 0.10) / 0.20) * 100
        
        weighted_margin = margin_score * 0.40
        score += weighted_margin
        breakdown.append(f"Margen ({margin_percent:.1%}): {margin_score:.0f}/100 pts -> +{weighted_margin:.1f}")

        # 2. COMPETITION DENSITY (30 pts)
        # Target: <5 competitors is great (Blue Ocean), >50 is bad (Red Ocean)
        comp_score = 0
        if competitor_count <= 5:
            comp_score = 100
        elif competitor_count >= 50:
            comp_score = 0
        else:
            # Linear decay
            comp_score = 100 - ((competitor_count - 5) / 45 * 100)
        
        weighted_comp = comp_score * 0.30
        score += weighted_comp
        breakdown.append(f"Competencia ({competitor_count}): {comp_score:.0f}/100 pts -> +{weighted_comp:.1f}")

        # 3. STABILITY / SPREAD (10 pts)
        # Target: spread_ratio < 0.2 (stable), > 1.0 (chaotic)
        stability_score = 0
        if spread_ratio <= 0.2:
            stability_score = 100
        elif spread_ratio >= 1.0:
            stability_score = 0
        else:
            stability_score = 100 - ((spread_ratio - 0.2) / 0.8 * 100)
            
        weighted_stability = stability_score * 0.10
        score += weighted_stability
        breakdown.append(f"Estabilidad Precios: {stability_score:.0f}/100 pts -> +{weighted_stability:.1f}")

        # 4. POSITION (20 pts)
        # Placeholder: assume 100 for now as we set the price optimally
        position_score = 100 
        weighted_pos = position_score * 0.20
        score += weighted_pos
        breakdown.append(f"Posicionamiento Estratégico: {position_score:.0f}/100 pts -> +{weighted_pos:.1f}")

        final_score = round(score)
        
        # Verdict
        if final_score >= 80:
            verdict = "🟢 Alta Oportunidad"
            action = "¡Lanzar Producto!"
        elif final_score >= 50:
            verdict = "🟡 Riesgo Medio"
            action = "Proceder con cautela"
        else:
            verdict = "🔴 No Recomendable"
            action = "Reevaluar costos o nicho"

        return {
            "score": final_score,
            "verdict": verdict,
            "action": action,
            "breakdown": breakdown
        }
