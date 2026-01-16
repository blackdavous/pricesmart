"""
Louder Price Intelligence - Streamlit Frontend
Interface for product price analysis and recommendations
"""
import streamlit as st
import requests
import re
from typing import Optional, Dict, Any
import time

import os
import time
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import statistics

# Try to load .env from backend
try:
    from dotenv import load_dotenv
    backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
    if backend_env_path.exists():
        load_dotenv(backend_env_path)
except ImportError:
    pass

# Configuration
API_BASE_URL = "http://localhost:8000"
BACKEND_AVAILABLE = False

# Check if backend is running
# try:
#     response = requests.get(f"{API_BASE_URL}/health", timeout=2)
#     BACKEND_AVAILABLE = response.status_code == 200
# except:
#     BACKEND_AVAILABLE = False
BACKEND_AVAILABLE = False # FORCED LOCAL MODE for debugging


def extract_product_info_from_url(url: str) -> Optional[Dict[str, str]]:
    """
    Extract product information from Mercado Libre URL.
    
    Examples:
    - https://www.mercadolibre.com.mx/rollo-de-cable-uso-rudo-calibre-14-awg-para-bocina-100m/p/MLM53396734
    - https://articulo.mercadolibre.com.mx/MLM-123456789-producto
    """
    # Extract product name from URL
    patterns = [
        r'mercadolibre\.com\.mx/([^/]+)/p/',  # /p/ URLs
        r'MLM-\d+-([^/\?]+)',  # MLM URLs
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            product_name = match.group(1)
            # Clean up: replace hyphens with spaces and capitalize
            product_name = product_name.replace('-', ' ').title()
            return {
                "name": product_name,
                "url": url
            }
    
    return None


def run_analysis_locally(product_name: str, cost: float, margin: float) -> Dict[str, Any]:
    """
    Run analysis locally using the agent modules directly.
    This is used when the backend API is not available.
    """
    import sys
    import os
    import asyncio
    
    # Add backend to path
    backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    
    try:
        # Import Pipeline
        # We need to ensure we can import from app.agents.pricing_pipeline
        # sys.path is already updated
        from app.agents.pricing_pipeline import PricingPipeline
        
        async def run():
            pipeline = PricingPipeline()
            
            # Run analysis
            # Ensure we pass all args
            pipeline_result = await pipeline.analyze_product(
                product_input=product_name,
                max_offers=25,
                cost_price=cost,
                target_margin=margin
            )
            
            # Extract Recommendation
            # Logic similar to API endpoint "analyze_adhoc"
            
            final_rec = pipeline_result.get("final_recommendation")
            
            if final_rec:
                # Extract competitors
                competitors = []
                steps = pipeline_result.get("pipeline_steps", {})
                if "matching" in steps and "comparable_offers" in steps["matching"]:
                     competitors = steps["matching"]["comparable_offers"]
                else:
                     # DO NOT FALLBACK TO SCRAPING.
                     # If matching fails or returns 0, we show 0.
                     # This prevents showing "garbage" raw results.
                     competitors = []
                     if "matching" not in steps:
                          # This implies pipeline crash in matching step
                          pass
                     
                stats = pipeline_result.get("pipeline_steps", {}).get("statistics", {})
                
                return {
                    "success": True,
                    "product_name": final_rec.get("product_name", product_name),
                    "recommended_price": final_rec.get("recommended_price"),
                    "margin_percent": final_rec.get("margin_percent", final_rec.get("expected_margin_percent", 0)), # handle different keys
                    "confidence": final_rec.get("confidence_score", final_rec.get("confidence", "unknown")),
                    "market_position": final_rec.get("market_position", "unknown"),
                    "alternatives": [v for k,v in final_rec.get("alternative_prices", {}).items()] if isinstance(final_rec.get("alternative_prices"), dict) else final_rec.get("alternative_prices", []),
                    "reasoning": final_rec.get("reasoning"),
                    "statistics": stats,
                    "competitors_analyzed": final_rec.get("competitor_sample_size", len(competitors)),
                    "competitors": competitors,
                    "currency": final_rec.get("currency", "MXN"),
                    "competitors": competitors,
                    "currency": final_rec.get("currency", "MXN"),
                    # Map the new profitability key from pipeline result
                    "profitability": pipeline_result.get("profitability"),
                    "viability": final_rec.get("viability"),
                    "pivot_product": pipeline_result.get("pipeline_steps", {}).get("pivot_product", {}),
                    "pipeline_steps": pipeline_result.get("pipeline_steps", {}),
                    "_debug_mode_forced": True
                }
            else:
                errors = pipeline_result.get("errors", [])
                error_msg = "; ".join(errors) if errors else "No detailed error"
                return {
                    "success": False,
                    "error": f"No pipeline recommendation: {error_msg}"
                }
        
        # Run async function
        result = asyncio.run(run())
        
        # DEBUG: Print keys to console/logs
        # print("DEBUG RESULT KEYS:", result.keys())
        # if "pivot_product" in result:
        #      print("DEBUG MATCHING STATS:", result.get("pivot_product", "No pivot"))
        
        return result
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": f"{str(e)}"
        }


def main():
    st.set_page_config(
        page_title="Price Smart IA",
        page_icon="💰",
        layout="wide"
    )
    
    # Header
    st.title("💰 Price Smart IA")
    st.markdown("**Análisis inteligente de precios para saber si conviene vender en mercadolibre**")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # API Key handling for Local Mode
        if not BACKEND_AVAILABLE:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                st.warning("⚠️ Se requiere API Key de OpenAI")
                api_key_input = st.text_input(
                    "OpenAI API Key", 
                    type="password", 
                    help="Ingresa tu clave sk-..."
                )
                if api_key_input:
                    os.environ["OPENAI_API_KEY"] = api_key_input
                    st.success("API Key guardada temporalmente")
            else:
                st.caption("🔑 API Key detectada")

        
        # Backend status
        if BACKEND_AVAILABLE:
            st.success("✅ Backend conectado")
            # --- DEBUG: Show API Token Status ---
            # Ideally this would come from a /health/config endpoint, but for now we assume 
            # if user put it in Coolify Env, backend has it.
            # We can't check backend env from frontend easily in this architecture without an endpoint.
            # However, we can add a text reminding them.
            st.caption("ℹ️ Asegúrate de tener `ML_ACCESS_TOKEN` en Coolify Variables si ves bloqueos.")
        else:
            st.warning("⚠️ Modo local (sin API)")
            st.caption("El análisis se ejecutará directamente")
        
        st.divider()
        
        # Cost and margin inputs
        st.subheader("Parámetros del producto")
        
        product_cost = st.number_input(
            "💵 Costo del producto (MXN)",
            min_value=0.0,
            value=500.0,
            step=50.0,
            help="Costo de adquisición o fabricación"
        )
        
        target_margin = st.number_input(
            "📈 Margen objetivo (%)",
            min_value=0.0,
            max_value=500.0,
            value=40.0,
            step=5.0,
            help="Margen de ganancia deseado"
        )
        
        st.divider()
        
        # Info section
        st.subheader("ℹ️ Información")
        st.caption("""
        **Cómo usar:**
        1. Ingresa un link de ML o nombre del producto
        2. Ajusta costo y margen deseado
        3. Haz clic en Analizar
        4. Obtén tu recomendación de precio
        
        **Posicionamiento:**
        - 🟢 Budget: 25° percentil
        - 🔵 Competitive: 50° percentil  
        - 🟠 Premium: 75° percentil
        - 🟣 Luxury: 90° percentil
        """)
    
    # Main content area
    st.divider()
    
    # Product input section
    st.header("🔍 Buscar Producto")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        product_input = st.text_input(
            "Ingresa el link de Mercado Libre o nombre del producto",
            placeholder="https://www.mercadolibre.com.mx/producto... o 'Cable para bocina calibre 14'",
            help="Puedes pegar un link completo de Mercado Libre o escribir el nombre del producto"
        )
    
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        analyze_button = st.button("🚀 Analizar", type="primary", use_container_width=True)
    
    # Process input when button is clicked
    if analyze_button and product_input:
        
        # Determine if input is URL or product name
        product_name = product_input
        is_url = False
        
        if "mercadolibre.com" in product_input.lower():
            is_url = True
            extracted = extract_product_info_from_url(product_input)
            if extracted:
                product_name = extracted["name"]
                st.info(f"📦 Producto detectado: **{product_name}**")
            else:
                st.warning("⚠️ No se pudo extraer el nombre del producto del link. Usando link completo.")
        
        # Progress indicator
        with st.spinner(f"🔄 Analizando **{product_name}**..."):
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("⏳ Buscando competidores en Mercado Libre...")
                progress_bar.progress(20)
                time.sleep(0.5)
                
                # Run analysis
                if BACKEND_AVAILABLE:
                    # Use API
                    status_text.text("📡 Conectando con API...")
                    progress_bar.progress(40)
                    
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/api/agents/analyze-adhoc",
                            json={
                                "product_input": product_input,
                                "cost": product_cost,
                                "margin": target_margin
                            },
                            timeout=180
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                        else:
                            st.error(f"❌ Error en la API: {response.text}")
                            st.stop()
                    except Exception as e:
                            st.error(f"❌ Error de conexión: {str(e)}")
                            st.stop()
                else:
                    # Run locally
                    status_text.text("🧮 Calculando estadísticas (DEMO LOCAL)...")
                    progress_bar.progress(60)
                    
                    # Pass the full input (URL or Name) to the pipeline
                    # The pipeline handles URL detection internally!
                    input_to_pipeline = product_input if is_url else product_name
                    
                    result = run_analysis_locally(input_to_pipeline, product_cost, target_margin)
                    
                    if not result.get("success"):
                        st.error(f"❌ Error en el análisis: {result.get('error')}")
                        st.stop()
                    
                # Store result in session state to persist across reruns (e.g. checkbox interactions)
                st.session_state.analysis_result = result
                st.session_state.analysis_performed = True
                
                # FINISH PROGRESS
                progress_bar.progress(100)
                status_text.success("¡Análisis Completado!")
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()

                
            except requests.exceptions.Timeout:
                st.error("⏱️ Timeout: El análisis tomó demasiado tiempo. Intenta nuevamente.")
                st.stop()
            except requests.exceptions.ConnectionError:
                st.error("🔌 Error de conexión: No se pudo conectar con el backend.")
                st.stop()
            except Exception as e:
                st.error(f"❌ Error inesperado: {str(e)}")
                st.exception(e)
                st.stop()

    elif analyze_button and not product_input:
        st.warning("⚠️ Por favor ingresa un producto o link de Mercado Libre")

    # --- DISPLAY RESULTS (Run always if state exists) ---
    if st.session_state.get("analysis_performed") and st.session_state.get("analysis_result"):
        result = st.session_state.analysis_result
        
        # Display results
        st.divider()
        # Display results
        st.divider()
        st.header("📊 Resultados del Análisis")
        
        # --- PIVOT PRODUCT HEADER ---
        pivot = result.get("pivot_product", {})
        if pivot and pivot.get("title"):
             with st.container():
                  c_img, c_info = st.columns([1, 4])
                  with c_img:
                       if pivot.get("image_url"):
                           st.image(pivot.get("image_url"), width=150)
                  with c_info:
                       st.info(f"🔎 Producto Analizado: **{pivot.get('title')}**")
                       st.markdown(f"**Precio Actual:** ${pivot.get('price', 0):,.2f}")
                       #st.caption(f"ID: {pivot.get('product_id')}")
        
        # Main recommendation card
        st.subheader("💡 Recomendación de Precio")
        
        rec_col1, rec_col2 = st.columns([1, 1])
        
        with rec_col1:
            st.markdown("#### 💰 Análisis de Rentabilidad Real (2026)")
            # Use 'profitability' key (new financial logic) or fallback to 'viability' if it contains the Dict structure (legacy safety)
            profit_data = result.get("profitability", {})
            if not profit_data and isinstance(result.get("viability"), dict) and "net_profit" in result["viability"]:
                 profit_data = result["viability"]
            
            if profit_data:
                breakdown = profit_data.get("breakdown", {})
                
                # Show key metrics first
                m1, m2, m3 = st.columns(3)
                m1.metric("Utilidad Neta", f"${profit_data.get('net_profit', 0):,.2f}", f"{profit_data.get('net_margin', 0)}% Neto")
                m2.metric("ROI", f"{profit_data.get('roi', 0)}%")
                m3.caption("Basado en Electrónica (15%) + Envío 1kg + Impuestos")
                
                # DEBUG: Show what data we have
                with st.expander("🔍 Debug: Ver datos de rentabilidad"):
                    st.json(profit_data)
                
                # Create DataFrame for detailed breakdown
                if breakdown:
                    import pandas as pd
                    rows = []
                    
                    if isinstance(breakdown, dict):
                        for k, v in breakdown.items():
                            rows.append({"Concepto": k, "Monto": f"${v:,.2f}"})
                    elif isinstance(breakdown, list):
                        # Should not happen with new key, but keeping safety
                        st.caption(f"Financial breakdown unavailable (Format: {type(breakdown)})")
                    
                    if rows:
                        df_costs = pd.DataFrame(rows)
                        st.table(df_costs)
            else:
                st.warning("⚠️ Para ver tu utilidad neta, por favor ingresa el **Costo del Producto** en el panel lateral.")

        with rec_col2:
            st.markdown("#### 💡 Estrategia de Precios")
            st.metric(
                "Precio Recomendado",
                f"${result.get('recommended_price', 0):,.2f} {result.get('currency', 'MXN')}",
                delta=f"{result.get('margin_percent', 0):.1f}% Margen"
            )
            
            st.info(f"**Razonamiento:** {result.get('reasoning', ['No disponible'])[0]}")
            
            confidence = result.get('confidence', 'unknown').upper()
            st.caption(f"Nivel de Confianza: **{confidence}**")
        
        # --- NEW SECTION: COMPETITORS ---
        st.divider()
        st.subheader("🔍 Competidores Detectados")
        
        competitors = result.get("competitors", [])
        
        # Initialize stats_clean from backend result
        stats = result.get('statistics', {})
        stats_clean = stats.get('overall', {}).get('stats_clean', {}) or stats.get('overall', {}).get('stats_all', {})
        
        # Initialize variable for prices
        prices = []
        
        if competitors:
            import pandas as pd
            
            # Create clean dataframe for display
            df_comp = pd.DataFrame(competitors)
            
            # Initialize 'Incluir' checkbox if not exists
            if "Incluir" not in df_comp.columns:
                df_comp.insert(0, "Incluir", True)

            # Select/Rename relevant columns if they exist
            cols_to_show = ["Incluir"] # Always start with Checkbox
            rename_map = {}
            
            if "image_url" in df_comp.columns: cols_to_show.append("image_url"); rename_map["image_url"] = "Foto"
            if "title" in df_comp.columns: cols_to_show.append("title"); rename_map["title"] = "Producto"
            if "price" in df_comp.columns: cols_to_show.append("price"); rename_map["price"] = "Precio"
            if "seller_name" in df_comp.columns: cols_to_show.append("seller_name"); rename_map["seller_name"] = "Vendedor"
            if "url" in df_comp.columns: cols_to_show.append("url"); rename_map["url"] = "Link"
            
            df_display = df_comp[cols_to_show].rename(columns=rename_map)
            
            st.caption("📝 Desmarca los productos que no sean competencia para recalcular las estadísticas.")
            
            # INTERACTIVE EDITOR
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "Incluir": st.column_config.CheckboxColumn("Incluir", help="Desmarca para excluir del análisis", width="small"),
                    "Foto": st.column_config.ImageColumn("Foto", help="Imagen del producto", width="small"),
                    "Link": st.column_config.LinkColumn("Enlace"),
                    "Precio": st.column_config.NumberColumn(format="$%.2f"),
                    "Producto": st.column_config.TextColumn("Producto", width="large"),
                },
                use_container_width=True,
                hide_index=True,
                key="competitors_editor"
            )
            
            # FILTER LOGIC: Get prices ONLY from included rows
            included_rows = edited_df[edited_df["Incluir"] == True]
            prices = included_rows["Precio"].tolist()
            
            # Recalculate simple stats for display if changed
            # Update stats variable to reflect manual changes in charts/metrics below
            if prices:
                import statistics
                new_min = min(prices)
                new_max = max(prices)
                new_avg = statistics.mean(prices)
                new_median = statistics.median(prices)
                
                # Hacky but effective for UI update without backend recall
                stats_clean = {
                    "min": new_min, "max": new_max, "mean": new_avg, "median": new_median,
                    "q1": float(statistics.median(sorted(prices)[:len(prices)//2])) if len(prices) > 1 else 0, # approx
                    "q3": float(statistics.median(sorted(prices)[len(prices)//2:])) if len(prices) > 1 else 0
                }
                
                # RECALCULATE RECOMMENDATION DYNAMICALLY
                # Simple strategy: Match median or slightly above depending on margin
                # This mimics the backend logic but client-side for interactivity
                rec_price_dynamic = new_median
                
                # If target margin is high, maybe aim for 75th percentile? 
                # For now, let's stick to median to be safe/competitive as per standard strategy
                
                if len(included_rows) < len(df_display):
                    st.success(f"🔄 Análisis actualizado: {len(included_rows)} productos seleccionados.")
                    # Override the result['recommended_price'] for display
                    result['recommended_price'] = rec_price_dynamic
                    
                    # Update margin percent based on new price
                    if product_cost > 0:
                        new_margin = ((rec_price_dynamic - product_cost) / product_cost) * 100
                        result['margin_percent'] = new_margin
                    
                    # Add reasoning
                    original_reasoning = result.get('reasoning', [])
                    if isinstance(original_reasoning, str):
                        original_reasoning = [original_reasoning]
                    elif original_reasoning is None:
                        original_reasoning = []
                        
                    result['reasoning'] = [f"Recalculado basado en selección manual (Mediana: ${new_median:,.2f})"] + original_reasoning
            
        else:
            st.info("No se encontraron detalles de competidores para mostrar en tabla.")
            prices = [] # Ensure prices is defined

        # --- EXCLUDED COMPETITORS SECTION ---
        st.divider()
        st.subheader("🚫 Competidores Descartados")
        
        # Get excluded offers from pipeline steps
        excluded_competitors = []
        pipeline_steps = result.get("pipeline_steps", {})
        if "matching" in pipeline_steps:
            excluded_competitors = pipeline_steps["matching"].get("excluded_offers", [])
        
        if excluded_competitors:
            import pandas as pd
            
            # Create dataframe for excluded competitors
            df_excluded = pd.DataFrame(excluded_competitors)
            
            # Initialize 'Incluir' checkbox as FALSE (unchecked by default)
            if "Incluir" not in df_excluded.columns:
                df_excluded.insert(0, "Incluir", False)
            
            # Select/Rename relevant columns
            cols_to_show_exc = ["Incluir"]
            rename_map_exc = {}
            
            if "image_url" in df_excluded.columns: cols_to_show_exc.append("image_url"); rename_map_exc["image_url"] = "Foto"
            if "title" in df_excluded.columns: cols_to_show_exc.append("title"); rename_map_exc["title"] = "Producto"
            if "price" in df_excluded.columns: cols_to_show_exc.append("price"); rename_map_exc["price"] = "Precio"
            if "exclusion_reason" in df_excluded.columns: cols_to_show_exc.append("exclusion_reason"); rename_map_exc["exclusion_reason"] = "Razón de Exclusión"
            if "seller_name" in df_excluded.columns: cols_to_show_exc.append("seller_name"); rename_map_exc["seller_name"] = "Vendedor"
            if "url" in df_excluded.columns: cols_to_show_exc.append("url"); rename_map_exc["url"] = "Link"
            
            df_excluded_display = df_excluded[cols_to_show_exc].rename(columns=rename_map_exc)
            
            st.caption("💡 Marca los productos que SÍ son competencia para incluirlos en el análisis.")
            
            # INTERACTIVE EDITOR for excluded
            edited_df_excluded = st.data_editor(
                df_excluded_display,
                column_config={
                    "Incluir": st.column_config.CheckboxColumn("Incluir", help="Marca para incluir en el análisis", width="small"),
                    "Foto": st.column_config.ImageColumn("Foto", help="Imagen del producto", width="small"),
                    "Link": st.column_config.LinkColumn("Enlace"),
                    "Precio": st.column_config.NumberColumn(format="$%.2f"),
                    "Producto": st.column_config.TextColumn("Producto", width="medium"),
                    "Razón de Exclusión": st.column_config.TextColumn("Motivo", width="medium"),
                },
                use_container_width=True,
                hide_index=True,
                key="excluded_competitors_editor"
            )
            
            # If any excluded items are now included, add them to the price calculation
            newly_included = edited_df_excluded[edited_df_excluded["Incluir"] == True]
            if len(newly_included) > 0:
                newly_included_prices = newly_included["Precio"].tolist()
                prices.extend(newly_included_prices)
                
                st.success(f"✅ {len(newly_included)} productos descartados incluidos en el análisis.")
                
                # Recalculate stats with the newly included prices
                if prices:
                    import statistics
                    new_min = min(prices)
                    new_max = max(prices)
                    new_avg = statistics.mean(prices)
                    new_median = statistics.median(prices)
                    
                    stats_clean = {
                        "min": new_min, "max": new_max, "mean": new_avg, "median": new_median,
                        "q1": float(statistics.median(sorted(prices)[:len(prices)//2])) if len(prices) > 1 else 0,
                        "q3": float(statistics.median(sorted(prices)[len(prices)//2:])) if len(prices) > 1 else 0
                    }
                    
                    rec_price_dynamic = new_median
                    result['recommended_price'] = rec_price_dynamic
                    
                    if product_cost > 0:
                        new_margin = ((rec_price_dynamic - product_cost) / product_cost) * 100
                        result['margin_percent'] = new_margin
                    
                    original_reasoning = result.get('reasoning', [])
                    if isinstance(original_reasoning, str):
                        original_reasoning = [original_reasoning]
                    elif original_reasoning is None:
                        original_reasoning = []
                    
                    result['reasoning'] = [f"Recalculado incluyendo {len(newly_included)} productos previamente descartados (Mediana: ${new_median:,.2f})"] + original_reasoning
        else:
            st.info("No hay competidores descartados para mostrar.")

        # --- NEW SECTION: CHARTS ---
        st.divider()
        st.subheader("📊 Análisis Gráfico")
        
        # Use stats_clean (either from backend or recalculated)
        # stats = result.get('statistics', {}) # Accessed above but maybe cleaner here
        # stats_clean is now potentially overwritten by interactive logic above
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("##### Distribución de Precios")
            # Histogram use prices list calculated above
            
            if prices:
                fig_hist = px.histogram(
                    x=prices, 
                    nbins=15, 
                    labels={'x': 'Precio (MXN)', 'y': 'Frecuencia'},
                    title="Histograma de Competidores",
                    color_discrete_sequence=['#3b82f6']
                )
                # Add vertical line for recommended price
                recommended = result.get('recommended_price')
                if recommended:
                    fig_hist.add_vline(x=recommended, line_dash="dash", line_color="green", annotation_text="Recomendado")
                
                st.plotly_chart(fig_hist, use_container_width=True)
            else:
                st.warning("No hay datos suficientes para la gráfica.")
        
        with col_chart2:
                st.markdown("##### Posición de Mercado")
                # Box Plot or Gauge
                if stats_clean:
                    min_p = stats_clean.get("min", 0)
                    max_p = stats_clean.get("max", 0)
                    median_p = stats_clean.get("median", 0)
                    q1 = stats_clean.get('q1', 0)
                    q3 = stats_clean.get('q3', 0)
                    
                    fig_box = go.Figure()
                    fig_box.add_trace(go.Box(
                        y=prices,
                        name="Mercado",
                        boxpoints='all',
                        jitter=0.3,
                        pointpos=-1.8,
                        marker_color='#6366f1'
                    ))
                    
                    recommended = result.get('recommended_price')
                    if recommended:
                        fig_box.add_hline(y=recommended, line_dash="dash", line_color="green", annotation_text=f"Tú: ${recommended:,.0f}")
                        
                    st.plotly_chart(fig_box, use_container_width=True)


        st.divider()
        
        # Statistics section (Text)
        col_stats1, col_stats2 = st.columns(2)
        
        with col_stats1:
            st.subheader("🔢 Métricas Detalladas")
            
            st.write(f"**📦 Muestra:** {len(prices)} productos (seleccionados)")
            if stats_clean:
                st.write(f"**💵 Mínimo:** ${stats_clean.get('min', 0):,.2f}")
                st.write(f"**📊 Mediana:** ${stats_clean.get('median', 0):,.2f}")
                st.write(f"**📈 Promedio:** ${stats_clean.get('mean', 0):,.2f}")
                st.write(f"**💰 Máximo:** ${stats_clean.get('max', 0):,.2f}")
            else:
                    st.write(f"**💵 Mínimo:** ${stats.get('min_price', 0):,.2f} MXN")
                    st.write(f"**📊 Mediana:** ${stats.get('median_price', 0):,.2f} MXN")
                    st.write(f"**📈 Promedio:** ${stats.get('mean_price', 0):,.2f} MXN")
                    st.write(f"**💰 Máximo:** ${stats.get('max_price', 0):,.2f} MXN")
        
        with col_stats2:
            st.subheader("🎯 Alternativas de Precio")
            
            alternatives = result.get('alternatives', [])
            
            if alternatives:
                for i, alt_price in enumerate(alternatives, 1):
                    alt_margin = ((alt_price - product_cost) / product_cost) * 100 if product_cost > 0 else 0
                    st.write(f"**{i}.** ${alt_price:,.2f} MXN _(margen: {alt_margin:.1f}%)_")
            else:
                st.info("No hay alternativas disponibles")
        
        st.divider()
        
        # Reasoning section
        st.subheader("💭 Razonamiento")
        reasoning_val = result.get('reasoning')
        if isinstance(reasoning_val, list):
            for r in reasoning_val:
                    st.info(r)
        else:
            st.info(str(reasoning_val))
        
        # Raw data expander (for debugging)
        with st.expander("🔧 Ver datos completos (debug)"):
            st.write("### Diagnóstico de Pipeline")
            steps = result.get("pipeline_steps", {})
            stats = result.get("statistics", {})
            
            scraper_count = "N/A"
            if "overall" in stats:
                 scraper_count = stats["overall"].get("total_offers", "Unknown")
            elif "scraping" in steps: # Legacy key
                 scraper_count = len(steps["scraping"].get("offers", []))
            
            match_step = steps.get("matching", {})
            comparable_count = match_step.get("comparable", "N/A")
            excluded_count = match_step.get("excluded", "N/A")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Scraper Encontró", scraper_count)
            c2.metric("Comparables", comparable_count)
            c3.metric("Excluidos", excluded_count)
            
            st.write("### JSON Completo")
            st.json(result)

        # --- NEW SECTION: COMISSION CALCULATOR ---
        st.divider()
        st.subheader("💰 Calculadora de Utilidad Real (2025)")
        
        try:
            # Import dynamically to avoid top-level issues if file missing
            import sys
            backend_path = Path(__file__).parent.parent / "backend"
            if str(backend_path) not in sys.path:
                sys.path.insert(0, str(backend_path))
            
            from app.services.commission_calculator import CommissionCalculator
            
            col_calc1, col_calc2, col_calc3 = st.columns(3)
            
            with col_calc1:
                calc_category_fee = st.selectbox(
                    "Categoría (Comisión Estimada)",
                    options=[10.0, 11.5, 13.0, 14.5, 15.0, 17.5, 19.0],
                    format_func=lambda x: f"{x}% (Ej: Electrónica, Hogar)",
                    index=4 # Default 15%
                )
                calc_listing_type = st.radio("Tipo Publicación", ["Clásica", "Premium"])
                
            with col_calc2:
                calc_weight = st.number_input("Peso Volumétrico (kg)", min_value=0.1, value=1.0, step=0.5)
                calc_reputation = st.selectbox("Tu Reputación", ["MercadoLider", "Green", "Yellow", "Orange/Red"], index=1)
                
            with col_calc3:
                # Use recommended price by default, or cost if no recommendation
                default_price = result.get("recommended_price") or (product_cost * 1.2)
                st.caption("Ajusta los valores para simular:")
                calc_price = st.number_input("Precio de Venta (MXN)", value=float(default_price), step=10.0)
                calc_cost = st.number_input("Costo Producto (MXN)", value=float(product_cost), step=10.0)

            # Calculate
            breakdown = CommissionCalculator.calculate_profit(
                selling_price=calc_price,
                cost_of_goods=calc_cost,
                weight_kg=calc_weight,
                category_fee_percent=calc_category_fee,
                reputation=calc_reputation,
                listing_type=calc_listing_type
            )
            
            # Display Results
            st.markdown("#### Resultado Neto")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Precio Venta", f"${breakdown.selling_price:,.2f}")
            c2.metric("Utilidad Neta", f"${breakdown.net_profit:,.2f}", delta=f"{breakdown.return_on_investment:.1f}% Retorno (ROI)")
            c3.metric("Margen (Ventas)", f"{breakdown.net_margin_percent}%", help="Utilidad / Precio Venta")
            c4.metric("Comisión + Envío", f"-${(breakdown.gross_commission + breakdown.shipping_cost):,.2f}", delta_color="inverse")
            
            # c4 previously held just shipping, condensed to make room for ROI or just add stats elsewhere

            
            # Detail Table
            st.caption("Desglose detallado (incluyendo impuestos IVA 8% / ISR 2.5%)")
            st.dataframe([breakdown.breakdown], use_container_width=True)
            
            if breakdown.net_profit < 0:
                st.error("⚠️ Estás perdiendo dinero con este precio.")
            elif breakdown.net_margin_percent < 20: 
                    st.warning("⚠️ Margen bajo (<20%).")
            else:
                st.success("✅ Margen saludable.")
                
        except Exception as e:
            st.error(f"Error cargando calculadora: {str(e)}")
            st.exception(e)
    
    elif analyze_button and not product_input:
        st.warning("⚠️ Por favor ingresa un producto o link de Mercado Libre")
    
    # Footer
    st.divider()
    st.caption("💡 **Louder Price Intelligence** - Análisis de precios basado en IA | Versión 0.1.0")


if __name__ == "__main__":
    main()
