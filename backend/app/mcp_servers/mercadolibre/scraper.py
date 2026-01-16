import re
import json
import time
import asyncio
import random
# from httpx import AsyncClient, Timeout
from curl_cffi.requests import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

from .models import IdentifiedProduct, Offer, ScrapingResult
from app.core.logging import get_logger
from dataclasses import dataclass

logger = get_logger(__name__)


@dataclass
class ProductDetails:
    """Detailed information extracted from a specific product page."""
    product_id: str
    title: str
    price: float
    currency: str
    condition: str
    brand: Optional[str]
    model: Optional[str]
    category: Optional[str]
    attributes: Dict[str, Any]  # Technical specifications
    description: Optional[str]
    images: List[str]
    seller_name: Optional[str]
    permalink: str
    image_url: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "product_id": self.product_id,
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "condition": self.condition,
            "brand": self.brand,
            "model": self.model,
            "category": self.category,
            "attributes": self.attributes,
            "description": self.description,
            "images": self.images,
            "seller_name": self.seller_name,
            "permalink": self.permalink,
            "image_url": self.image_url
        }


# User Agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


# Accessory keywords to filter out
ACCESSORY_NEGATIVES = [
    "funda", "case", "carcasa", "protector", "mica", "glass", "templado", "cable",
    "adaptador", "cargador", "base", "soporte", "refacción", "repuesto", "control",
    "almohadillas", "earpads", "estuche", "solo caja"
]


def normalize_text(s: str) -> str:
    """Normalize text: lowercase and single spaces."""
    return re.sub(r"\s+", " ", s.lower().strip())


def normalize_model(s: str) -> str:
    """Normalize model: alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", normalize_text(s))


def extract_product(description: str) -> IdentifiedProduct:
    """
    Extract product brand and model from description.
    
    Args:
        description: Product description or name
        
    Returns:
        IdentifiedProduct with brand, model, and signature
    """
    d = normalize_text(description)
    
    # Detect brand (can be extended)
    brand = "sony" if " sony " in f" {d} " else None
    
    # Extract model pattern (e.g., "WH-1000XM5", "MDR-ZX110")
    mm = re.search(r"\b([a-z]{1,4}\s*[-]?\s*\d{2,6}\s*[a-z]{0,6}\d*)\b", d)
    model = mm.group(1) if mm else None
    model_norm = normalize_model(model) if model else None
    
    # Create signature
    signature = " ".join([x for x in [brand, model] if x]).strip() or description.strip()
    
    return IdentifiedProduct(brand, model, model_norm, signature)


def match_title(title: str, product: IdentifiedProduct) -> bool:
    """
    Check if a title matches the target product.
    
    Args:
        title: Product title from listing
        product: Target product to match
        
    Returns:
        True if title matches product
    """
    t = normalize_text(title)
    
    # Filter out accessories
    if any(x in t for x in ACCESSORY_NEGATIVES):
        return False
    
    # Match by model (strongest match)
    if product.model_norm:
        return product.model_norm in normalize_model(title)
    
    # Match by brand (weaker match)
    if product.brand:
        return product.brand in t
    
    # Default: accept (for generic searches)
    return True


def listing_url(query: str) -> str:
    """
    Generate Mercado Libre listing URL from query.
    
    Args:
        query: Search query
        
    Returns:
        ML listing URL
    """
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_text(query)).strip("-")
    return f"https://listado.mercadolibre.com.mx/{slug}"


def extract_js_object_by_brackets(text: str, start_idx: int) -> Optional[str]:
    """
    Extract JavaScript object by balanced bracket matching.
    More robust than regex for nested objects.
    
    Args:
        text: Full text containing JS object
        start_idx: Index of opening brace '{'
        
    Returns:
        Extracted JS object string or None
    """
    i = start_idx
    if i < 0 or i >= len(text) or text[i] != "{":
        return None
    
    depth = 0
    in_str = False
    esc = False
    quote = ""
    
    for j in range(i, len(text)):
        ch = text[j]
        
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        else:
            if ch in ("'", '"'):
                in_str = True
                quote = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[i:j+1]
    
    return None


def extract_preloaded_state(html: str) -> Optional[dict]:
    """
    Extract __PRELOADED_STATE__ from HTML.
    
    This is a JavaScript object embedded in the page with product data.
    
    Args:
        html: Page HTML
        
    Returns:
        Parsed dict or None
    """
    m = re.search(r"__PRELOADED_STATE__\s*=\s*", html)
    if not m:
        return None
    
    k = m.end()
    brace = html.find("{", k)
    if brace == -1:
        return None
    
    obj_str = extract_js_object_by_brackets(html, brace)
    if not obj_str:
        return None
    
    # Try direct JSON parse
    try:
        return json.loads(obj_str)
    except Exception:
        pass
    
    # Clean common JS issues
    cleaned = obj_str
    cleaned = re.sub(r"\bundefined\b", "null", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    
    try:
        return json.loads(cleaned)
    except Exception:
        logger.warning("Failed to parse __PRELOADED_STATE__")
        return None


def extract_jsonld_nodes(html: str) -> List[Dict[str, Any]]:
    """
    Extract JSON-LD nodes from HTML (fallback method).
    
    Args:
        html: Page HTML
        
    Returns:
        List of JSON-LD nodes with product data
    """
    nodes = []
    
    for m in re.finditer(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        
        # Traverse object tree to find product nodes
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if ("name" in x or "title" in x) and ("offers" in x or "price" in x):
                    nodes.append(x)
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(x, list):
                for v in x:
                    if isinstance(v, (dict, list)):
                        stack.append(v)
    
    return nodes


def offers_from_state(state: dict, product: IdentifiedProduct, limit: int = 150) -> List[Offer]:
    """
    Extract offers from __PRELOADED_STATE__.
    
    Args:
        state: Parsed __PRELOADED_STATE__ dict
        product: Target product for filtering
        limit: Max offers to extract
        
    Returns:
        List of Offer objects
    """
    out: List[Offer] = []
    stack = [state]
    
    while stack and len(out) < limit:
        x = stack.pop()
        
        if isinstance(x, dict):
            title = x.get("title") or x.get("name")
            price = x.get("price")
            if isinstance(price, dict):
                price = price.get("amount") or price.get("value")
            url = x.get("permalink") or x.get("url") or ""
            item_id = x.get("id") or x.get("item_id") or ""
            
            if title and price is not None:
                try:
                    p = float(price)
                    if match_title(str(title), product):
                        out.append(Offer(
                            title=str(title),
                            price=p,
                            condition=str(x.get("condition") or "unknown"),
                            url=str(url),
                            item_id=str(item_id),
                            source="preloaded_state",
                        ))
                except Exception:
                    pass
            
            for v in x.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(x, list):
            for v in x:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    
    return out


def offers_from_jsonld(nodes: List[Dict[str, Any]], product: IdentifiedProduct, limit: int = 150) -> List[Offer]:
    """
    Extract offers from JSON-LD nodes (fallback).
    
    Args:
        nodes: JSON-LD nodes
        product: Target product
        limit: Max offers
        
    Returns:
        List of Offer objects
    """
    out: List[Offer] = []
    
    for node in nodes:
        title = node.get("name") or node.get("title")
        url = node.get("url") or ""
        offers = node.get("offers")
        cand_prices = []
        
        if isinstance(offers, dict):
            cand_prices.append(offers.get("price"))
            url = offers.get("url") or url
        elif isinstance(offers, list):
            for o in offers:
                if isinstance(o, dict):
                    cand_prices.append(o.get("price"))
                    if not url:
                        url = o.get("url") or url
        
        for pr in cand_prices:
            if title and pr is not None:
                try:
                    p = float(pr)
                    if match_title(str(title), product):
                        out.append(Offer(
                            title=str(title),
                            price=p,
                            condition="unknown",
                            url=str(url),
                            item_id="",
                            source="jsonld",
                        ))
                        if len(out) >= limit:
                            return out
                except Exception:
                    continue
    
    return out


class MLWebScraper:
    """
    Mercado Libre web scraper.
    Extracts product data from HTML without API.
    Uses curl_cffi to impersonate Chrome and bypass Captchas.
    """
    
    def __init__(self):
        self.timeout = 30.0

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with random User-Agent."""
        headers = DEFAULT_HEADERS.copy()
        headers["User-Agent"] = random.choice(USER_AGENTS)
        return headers

    async def _fetch_url(self, url: str) -> str:
        """
        Fetch URL using curl_cffi to mimic real Chrome browser.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content
            
        Raises:
            Exception: If request fails after retries
        """
        max_retries = 3
        base_delay = 2
        
        # We create a new session for each fetch to avoid stale states/cookies if desired,
        # or we could keep one. For simplicity and robustness, new session per request.
        async with AsyncSession(impersonate="chrome120", timeout=self.timeout) as client:
            for attempt in range(max_retries):
                try:
                    headers = self._get_headers()
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        return response.text
                    
                    if response.status_code in (429, 503):
                        # Rate limit or server busy
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Got {response.status_code} for {url}. Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                        continue
                     
                    if response.status_code == 404:
                         raise Exception(f"404 Not Found: {url}")
                         
                    # Standard error raising for other codes
                    response.raise_for_status()
                    
                except Exception as e:
                    logger.warning(f"Request error for {url}: {e}. Attempt {attempt + 1}/{max_retries}")
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(1)
            
            raise Exception(f"Failed to fetch {url} after {max_retries} attempts")
    
    async def search_products(
        self,
        description: str,
        max_offers: int = 25,
        timeout: int = 25
    ) -> ScrapingResult:
        """
        Search for products and extract offers from HTML.
        
        Args:
            description: Product description (e.g., "Sony WH-1000XM5 audifonos")
            max_offers: Maximum offers to return
            timeout: Request timeout in seconds
            
        Returns:
            ScrapingResult with offers and metadata
        """
        logger.info(
            "Starting ML web scraping",
            description=description,
            max_offers=max_offers
        )
        
        # Extract product info
        product = extract_product(description)
        url = listing_url(product.signature)
        
        logger.info(
            "Product identified",
            brand=product.brand,
            model=product.model,
            signature=product.signature,
            url=url
        )
        
        # Fetch HTML
        try:
            html = await self._fetch_url(url)
        except Exception as e:
            logger.error("Failed to fetch HTML", error=str(e), url=url)
            return ScrapingResult(
                identified_product=product,
                strategy="error",
                listing_url=url,
                offers=[],
                timestamp=datetime.now().isoformat()
            )
        
        offers: List[Offer] = []
        strategy = "none"
        
        # Try HTML parsing (BeautifulSoup) - Primary strategy for new layout
        if not offers:
            offers = offers_from_html(html, product, limit=max_offers)
            strategy = "html_parsing" if offers else "no_offers"
            if offers:
                logger.info(f"Extracted {len(offers)} offers from HTML parsing")

        # Try __PRELOADED_STATE__ (Legacy)
        if not offers:
            state = extract_preloaded_state(html)
            if isinstance(state, dict):
                offers = offers_from_state(state, product, limit=max_offers * 6)
                strategy = "preloaded_state"
                logger.info(f"Extracted {len(offers)} offers from __PRELOADED_STATE__")
        
        # Fallback to JSON-LD
        if not offers:
            nodes = extract_jsonld_nodes(html)
            offers = offers_from_jsonld(nodes, product, limit=max_offers * 6)
            strategy = "jsonld" if offers else strategy
            if offers:
                logger.info(f"Extracted {len(offers)} offers from JSON-LD")
        
        # Limit offers
        offers = offers[:max_offers]
        
        logger.info(
            "Scraping completed",
            strategy=strategy,
            offers_count=len(offers)
        )
        
        return ScrapingResult(
            identified_product=product,
            strategy=strategy,
            listing_url=url,
            offers=offers,
            timestamp=datetime.now().isoformat()
        )
    
    async def extract_product_details(self, product_url: str) -> Optional[ProductDetails]:
        """
        Extract detailed information from a specific product page.
        
        Hybrid Strategy:
        1. Check for ML_ACCESS_TOKEN env var.
        2. If present, extract ID and call API (Bypasses Blocking).
        3. If not, fallback to Scraping (HTML/JSON-LD).
        """
        logger.info("Extracting product details...", url=product_url)
        
        # 1. Extract Product ID (Always needed)
        product_id = ""
        match = re.search(r"ML[A-Z]-?\d+", product_url)
        if match:
            product_id = match.group(0).replace("-", "")
            
        # 2. Try API Strategy (If Token Exists)
        import os
        api_token = os.getenv("ML_ACCESS_TOKEN")
        api_error = None
        
        if api_token and product_id:
            logger.info(f"ML Protocol: Using API for pivot product {product_id}")
            try:
                details = await self._extract_details_from_api(product_id, api_token)
                if details:
                    details.permalink = product_url # Ensure original URL is kept
                    return details
            except Exception as e:
                api_error = str(e)
                logger.error(f"API Strategy failed, falling back to scraper: {e}")
        elif not api_token:
            api_error = "Token Env Var Missing"
        
        # 3. Fallback to Scraper Strategy
        try:
            html = await self._fetch_url(product_url)
        except Exception as e:
            logger.error(f"Failed to fetch product page: {e}")
            raise Exception(f"Network/Block Error: {str(e)} (API Context: {api_error})")
        
        # Try to extract from __PRELOADED_STATE__
        state = extract_preloaded_state(html)
        if state:
            details = self._extract_details_from_state(state, product_url)
            if details:
                return details
        
        # Fallback to JSON-LD
        nodes = extract_jsonld_nodes(html)
        if nodes:
            details = self._extract_details_from_jsonld(nodes, product_url)
            if details:
                return details
        
        # Fallback to HTML Parsing (BeautifulSoup)
        details = self._extract_details_from_html(html, product_url)
        if details:
            return details
        
        # If we got here, we have HTML but couldn't parse it.
        if "captcha" in html.lower() or "security" in html.lower():
             raise Exception(f"Blocked: MercadoLibre serving Captcha. (API Strategy Failed: {api_error})")
             
        raise Exception(f"Parsing Error: HTML length {len(html)} but no data found. (API Strategy Failed: {api_error}) Title: {BeautifulSoup(html, 'lxml').title.string if BeautifulSoup(html, 'lxml').title else 'No Title'}")

    async def _extract_details_from_api(self, item_id: str, token: str) -> Optional[ProductDetails]:
        """Fetch product details from official MercadoLibre API."""
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        async with AsyncSession(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                
                # Fetch Description
                desc_url = f"https://api.mercadolibre.com/items/{item_id}/description"
                desc_resp = await client.get(desc_url, headers=headers)
                description = desc_resp.json().get("plain_text", "") if desc_resp.status_code == 200 else ""

                attributes = {attr["id"]: attr.get("value_name") for attr in data.get("attributes", [])}
                
                return ProductDetails(
                    product_id=data.get("id"),
                    title=data.get("title"),
                    price=float(data.get("price", 0)),
                    currency=data.get("currency_id"),
                    condition=data.get("condition"),
                    brand=attributes.get("BRAND"),
                    model=attributes.get("MODEL"),
                    category=data.get("category_id"),
                    attributes=attributes,
                    description=description,
                    images=[p["url"] for p in data.get("pictures", [])],
                    seller_name=None, # API doesn't expose seller name directly in public item view sometimes
                    permalink=data.get("permalink"),
                    image_url=data.get("thumbnail")
                )
            elif resp.status_code == 403:
                raise Exception("API Token Refused (403)")
            elif resp.status_code == 404:
                return None
            else:
                raise Exception(f"API Error {resp.status_code}")

    def _extract_details_from_html(self, html: str, url: str) -> Optional[ProductDetails]:
        """Extract product details directly from HTML using BeautifulSoup."""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Debugging: Log what we are seeing
            page_title = soup.title.string if soup.title else "No Title"
            h1_text = soup.select_one('h1').get_text().strip() if soup.select_one('h1') else "No H1"
            logger.info(f"HTML Parsing Debug - Title: {page_title} | H1: {h1_text} | Length: {len(html)}")
            
            if "captcha" in page_title.lower() or "security" in page_title.lower():
                logger.error("SCRAPER BLOCKED: Captcha detected")
                return None

            # 1. Extract Title
            # Try multiple selectors for title
            title_tag = soup.select_one('.ui-pdp-title') or soup.find('h1', {'class': 'ui-pdp-title'}) or soup.select_one('h1')
            if not title_tag:
                logger.warning("Could not find title tag with primary selectors")
                return None
            title = title_tag.get_text().strip()
            
            # 2. Extract Price
            price = 0.0
            # Try specific price container first, then generic
            # Sometimes price is in meta tag
            meta_price = soup.find('meta', itemprop='price')
            if meta_price:
                try:
                    price = float(meta_price['content'])
                except:
                    pass
            
            if price == 0.0:
                price_fraction = soup.select_one('.ui-pdp-price__second-line .andes-money-amount__fraction')
                if not price_fraction:
                     price_fraction = soup.select_one('.andes-money-amount__fraction')
                
                if price_fraction:
                    try:
                        price = float(price_fraction.get_text().strip().replace('.', '').replace(',', ''))
                    except:
                        pass
            
            # 3. Extract Image
            image_url = None
            # Try meta tag first
            meta_image = soup.find('meta', property='og:image')
            if meta_image:
                image_url = meta_image['content']
            
            if not image_url:
                img_tag = soup.select_one('.ui-pdp-gallery__figure img')
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')

            # 4. Extract Product ID from URL
            product_id = ""
            match = re.search(r"ML[A-Z]-?\d+", url)
            if match:
                product_id = match.group(0).replace("-", "")
            
            # 5. Extract Attributes (Basic)
            attributes = {}
            # Try to grab specs table
            for row in soup.select('.ui-pdp-specs__table tr'):
                cols = row.select('th, td')
                if len(cols) == 2:
                    k = cols[0].get_text().strip()
                    v = cols[1].get_text().strip()
                    attributes[k] = v
            
            # Extract Brand/Model from attributes if available
            brand = attributes.get('Marca') or attributes.get('Brand')
            model = attributes.get('Modelo') or attributes.get('Model')

            return ProductDetails(
                product_id=product_id,
                title=title,
                price=price,
                currency="MXN", # Default for .com.mx
                condition="new", # Assumption if not found
                brand=brand,
                model=model,
                category=None,
                attributes=attributes,
                description=None,
                images=[image_url] if image_url else [],
                seller_name=None,
                permalink=url,
                image_url=image_url
            )
        except Exception as e:
            logger.error(f"Error extracting details from HTML: {e}")
            return None
    
    def _extract_details_from_state(self, state: dict, url: str) -> Optional[ProductDetails]:
        """Extract product details from __PRELOADED_STATE__."""
        try:
            # Navigate the state structure to find product info
            components = state.get("components", {})
            
            # Try different paths where product data might be
            product_data = None
            for key, value in components.items():
                if isinstance(value, dict) and "product" in value:
                    product_data = value.get("product")
                    break
                elif isinstance(value, dict) and "item" in value:
                    product_data = value.get("item")
                    break
            
            if not product_data:
                return None
            
            # Extract attributes
            attributes = {}
            if "attributes" in product_data:
                for attr in product_data.get("attributes", []):
                    if isinstance(attr, dict):
                        name = attr.get("name") or attr.get("id")
                        value = attr.get("value_name") or attr.get("value")
                        if name and value:
                            attributes[name] = value
            
            # Extract images
            images = []
            if "pictures" in product_data:
                for pic in product_data.get("pictures", []):
                    if isinstance(pic, dict) and "url" in pic:
                        images.append(pic["url"])
            
            return ProductDetails(
                product_id=product_data.get("id", ""),
                title=product_data.get("title", ""),
                price=float(product_data.get("price", 0)),
                currency=product_data.get("currency_id", "MXN"),
                condition=product_data.get("condition", "unknown"),
                brand=attributes.get("Marca") or attributes.get("BRAND"),
                model=attributes.get("Modelo") or attributes.get("MODEL"),
                category=product_data.get("category_id"),
                attributes=attributes,
                description=product_data.get("description"),
                images=images,
                seller_name=product_data.get("seller", {}).get("nickname") if isinstance(product_data.get("seller"), dict) else None,
                permalink=url,
                image_url=images[0] if images else None
            )
        except Exception as e:
            logger.error(f"Error extracting from state: {e}")
            return None
    
    def _extract_details_from_jsonld(self, nodes: List[dict], url: str) -> Optional[ProductDetails]:
        """Extract product details from JSON-LD."""
        try:
            # Find Product node
            product_node = None
            for node in nodes:
                if node.get("@type") == "Product":
                    product_node = node
                    break
            
            if not product_node:
                return None
            
            # Extract offers
            offers_data = product_node.get("offers", {})
            if isinstance(offers_data, list) and offers_data:
                offers_data = offers_data[0]
            
            price = 0.0
            currency = "MXN"
            if isinstance(offers_data, dict):
                price = float(offers_data.get("price", 0))
                currency = offers_data.get("priceCurrency", "MXN")
            
            # Extract brand
            brand_data = product_node.get("brand")
            brand = None
            if isinstance(brand_data, dict):
                brand = brand_data.get("name")
            elif isinstance(brand_data, str):
                brand = brand_data
            
            # Extract images
            images = []
            image_data = product_node.get("image", [])
            if isinstance(image_data, str):
                images = [image_data]
            elif isinstance(image_data, list):
                images = [img if isinstance(img, str) else img.get("url") for img in image_data if img]
            
            # Extract product ID from URL or sku
            product_id = product_node.get("sku", "")
            if not product_id:
                match = re.search(r"ML[A-Z]-?\d+", url)
                product_id = match.group(0).replace("-", "") if match else ""
            
            return ProductDetails(
                product_id=product_id,
                title=product_node.get("name", ""),
                price=price,
                currency=currency,
                condition=product_node.get("itemCondition", "unknown"),
                brand=brand,
                model=product_node.get("model"),
                category=product_node.get("category"),
                attributes={},  # JSON-LD typically doesn't have detailed attributes
                description=product_node.get("description"),
                images=images,
                seller_name=None,
                permalink=url
            )
        except Exception as e:
            logger.error(f"Error extracting from JSON-LD: {e}")
            return None


def offers_from_html(html: str, product: IdentifiedProduct, limit: int = 150) -> List[Offer]:
    """
    Extract offers by parsing HTML structure (BeautifulSoup).
    
    Args:
        html: Raw HTML
        product: Identified product for filtering
        limit: Max offers
        
    Returns:
        List of Offer objects
    """
    out: List[Offer] = []
    try:
        soup = BeautifulSoup(html, 'lxml')
        # Standard ML list items
        items = soup.select('.ui-search-layout__item')
        
        for item in items:
            try:
                # Extract Title
                title_tag = item.select_one('.ui-search-item__title') or item.select_one('.poly-component__title')
                if not title_tag:
                    continue
                title = title_tag.get_text().strip()
                
                # Extract Price
                price_text = "0"
                # Try finding the price container
                price_container = item.select_one('.ui-search-price__part') or item.select_one('.andes-money-amount')
                if price_container:
                     # Usually contains a fractional part class
                     fraction = price_container.select_one('.andes-money-amount__fraction')
                     if fraction:
                         price_text = fraction.get_text().strip().replace('.', '').replace(',', '')
                
                price = float(price_text)
                
                # Extract URL
                link_tag = item.select_one('a.ui-search-link') or item.select_one('a')
                url = link_tag.get('href') if link_tag else ""
                
                # Extract ID from URL if possible (MLM...) or use a hash
                item_id = ""
                match = re.search(r"ML[A-Z]-?\d+", url)
                if match:
                    item_id = match.group(0).replace("-", "")
                
                # Condition (ML usually puts it in a span like "Usado")
                # This is harder to find consistently, default to unknown
                condition = "unknown"
                
                # Extract Image URL
                image_url = None
                img_tag = item.select_one('img.ui-search-result-image__element') or item.select_one('.poly-component__picture')
                if img_tag:
                    image_url = img_tag.get('data-src') or img_tag.get('src')

                # Extract Seller Name
                seller_name = None
                seller_tag = item.select_one('.ui-search-official-store-label') or item.select_one('.poly-component__seller')
                if seller_tag:
                    seller_name = seller_tag.get_text().strip().replace("por ", "")
                
                # Extract Full Status
                is_full = False
                # 1. Look for text "Full"
                full_tag = item.select_one('.ui-search-item__fulfillment-label') or item.select_one('.poly-component__shipping-badge')
                if full_tag and "full" in full_tag.get_text().lower():
                    is_full = True
                
                # 2. Look for the Lightning Icon (SVG) usually associated with Full
                if not is_full:
                    # Generic check for SVG or icon container containing 'full' in class or aria-label
                    icon_full = item.select_one('span.ui-search-item__fulfillment-label svg')
                    if icon_full: is_full = True
                    
                    # New layout specific check
                    poly_shipping = item.select_one('.poly-component__shipping-badge')
                    if poly_shipping:
                        # Check for svg inside
                        if poly_shipping.select_one('svg') or "full" in poly_shipping.get_text().lower():
                            is_full = True

                # Extract Reviews
                reviews_count = 0
                stars = None
                
                # Stars (Rating)
                rating_tag = item.select_one('.ui-search-reviews__rating-number') or item.select_one('.poly-reviews__rating')
                if rating_tag:
                    try:
                        stars = float(rating_tag.get_text().strip())
                    except:
                        pass
                
                # Review Count
                reviews_tag = item.select_one('.ui-search-reviews__amount') or item.select_one('.poly-reviews__total')
                if reviews_tag:
                    try:
                        reviews_text = reviews_tag.get_text().strip().replace('(', '').replace(')', '')
                        reviews_count = int(reviews_text)
                    except:
                        pass
                        
                # Extract Sales Volume (e.g. "+1000 vendidos")
                sales_count = 0 # Approximate
                sales_tag = item.select_one('.ui-search-item__group__element.ui-search-item__group__element--mock_sold')
                if not sales_tag:
                    # Try finding text "vendidos" in any span
                    for span in item.find_all('span', string=re.compile(r'vendidos', re.IGNORECASE)):
                         sales_tag = span
                         break
                
                if sales_tag:
                    try:
                        txt = sales_tag.get_text().lower().replace('+', '').replace('vendidos', '').replace('mil', '000').strip()
                        sales_count = int(txt)
                    except:
                        pass

                if rating_tag:
                     try:
                         stars = float(rating_tag.get_text().strip())
                     except:
                         pass

                if match_title(title, product):
                    out.append(Offer(
                        title=title,
                        price=price,
                        condition=condition,
                        url=url,
                        item_id=item_id,
                        source="html_parsing",
                        image_url=image_url,
                        seller_name=seller_name,
                        is_full=is_full,
                        stars=stars,
                        reviews_count=reviews_count
                    ))
                    
                if len(out) >= limit:
                    break
                    
            except Exception as e:
                continue
                
    except Exception as e:
        logger.error(f"Error parsing HTML with BeautifulSoup: {e}")
        
    return out
