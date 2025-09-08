import requests
import cloudscraper
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import csv
import time
import re

# -------------------------
# Global sessions
# -------------------------
session = requests.Session()
session.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/115.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
})

# cloudscraper session (lazy init)
_cf_scraper = None
def get_cf_scraper():
    global _cf_scraper
    if _cf_scraper is None:
        _cf_scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    return _cf_scraper

# -------------------------
# Fetch helpers
# -------------------------
def fetch_url_basic(url, retries=3, delay=5, timeout=30):
    """Fetch with requests (normal sites)"""
    for i in range(retries):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[Basic] Error fetching {url}: {e}. Retry {i+1}/{retries} in {delay}s...")
            time.sleep(delay)
    raise Exception(f"Failed to fetch {url} after {retries} retries.")

def fetch_url_cf(url, retries=3, delay=5, timeout=30, headers=None):
    """Fetch with cloudscraper (Cloudflare-protected sites)."""
    scraper = get_cf_scraper()
    headers = headers or {}  # allow custom headers (e.g., Referer)

    for i in range(retries):
        try:
            response = scraper.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[CF] Error fetching {url}: {e}. Retry {i+1}/{retries} in {delay}s...")
            time.sleep(delay)
    raise Exception(f"Failed to fetch {url} after {retries} retries.")


def is_cloudflare_block(response):
    """Detect Cloudflare block pages"""
    if response is None:
        return False
    if response.status_code in (403, 503):
        text = response.text.lower()
        if "cloudflare" in text or "just a moment" in text or "attention required" in text:
            return True
    return False

def fetch_url(url, retries=3, delay=5, timeout=30, use_cloudflare=None, headers=None):
    """
    Unified fetch:
    - If use_cloudflare is True -> always use cloudscraper
    - If use_cloudflare is False -> always use requests
    - If use_cloudflare is None (default) -> try requests first, fallback to cloudscraper on block
    """
    headers = headers or {}

    if use_cloudflare is True:
        return fetch_url_cf(url, retries=retries, delay=delay, timeout=timeout, headers=headers)

    if use_cloudflare is False:
        #return fetch_url_basic(url, retries=retries, delay=delay, timeout=timeout, headers=headers)
        return fetch_url_basic(url, retries=retries, delay=delay, timeout=timeout)

    # Auto-detect mode
    try:
        response = fetch_url_basic(url, retries=1, timeout=timeout, headers=headers)  # one try with requests
        if is_cloudflare_block(response):
            print(f"[AutoDetect] Cloudflare detected at {url}, switching to cloudscraper...")
            return fetch_url_cf(url, retries=retries, delay=delay, timeout=timeout, headers=headers)
        return response
    except Exception as e:
        print(f"[AutoDetect] Error with requests: {e}. Trying cloudscraper...")
        return fetch_url_cf(url, retries=retries, delay=delay, timeout=timeout, headers=headers)


# -------------------------
# HTML Parser (unchanged)
# -------------------------
class CustomHTMLParser(HTMLParser):
    def __init__(self, base_url, config):
        super().__init__()
        self.base_url = base_url
        self.config = config

        self.name_tag, self.name_attr, self.name_val = self._parse_tag(config["name"])
        self.link_tag, self.link_attr, self.link_val = self._parse_tag(config["link"])
        self.price_tag, self.price_attr, self.price_val = self._parse_tag(config["price"])
        self.next_tag, self.next_attr, self.next_val = self._parse_tag(config.get("next", "<a class='next'>"))

        self.in_title = False
        self.titles = []
        self.in_name = False
        self.in_link = False
        self.current_product_link = None
        self.in_price = False
        self.current_product = None
        self.product_data = []
        self.next_page = None

    def _parse_tag(self, tag_string):
        tag_string = tag_string.strip("<>").replace("'", '"')
        parts = tag_string.split(maxsplit=1)
        tag = parts[0]
        attr_name, attr_value = None, None
        if len(parts) > 1:
            attr = parts[1]
            if "=" in attr:
                attr_name, attr_value = attr.split("=", 1)
                attr_name = attr_name.strip()
                attr_value = attr_value.strip('"')
        return tag, attr_name, attr_value

    def _attr_match(self, tag, attrs, expected_tag, attr_name, attr_val):
        if tag != expected_tag:
            return False
        for (k, v) in attrs:
            if k == attr_name and attr_val in v:
                return True
        return False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if self._attr_match(tag, attrs, self.name_tag, self.name_attr, self.name_val):
            self.in_name = True
        if self._attr_match(tag, attrs, self.price_tag, self.price_attr, self.price_val):
            self.in_price = True

        href = None
        for (k, v) in attrs:
            if k == "href":
                href = v.strip()
        if tag == "a" and href and not href.startswith("#") and self.in_name:
            full_url = urljoin(self.base_url, href)
            self.in_link = True
            self.current_product_link = full_url

        if self._attr_match(tag, attrs, self.next_tag, self.next_attr, self.next_val):
            if href:
                self.next_page = urljoin(self.base_url, href)
            else:
                self.next_page = True

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self.in_title:
            self.titles.append(text)
        if self.in_name and self.in_link:
            self.current_product = {"name": text, "link": self.current_product_link, "price": None}
            self.product_data.append(self.current_product)
        if self.in_price and self.current_product:
            self.current_product["price"] = text

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == self.name_tag:
            self.in_name = False
        if tag == "a" and self.in_link:
            self.in_link = False
            self.current_product_link = None
        if tag == self.price_tag:
            self.in_price = False

# -------------------------
# Scrape functions
# -------------------------
def scrape_page(url, config, use_cloudflare=False, headers=None):
    """Scrape a single page, with optional headers (e.g., Referer for CF sites)."""
    response = fetch_url(url, use_cloudflare=use_cloudflare, headers=headers)
    parser = CustomHTMLParser(url, config)
    parser.feed(response.text)
    return {
        "titles": parser.titles,
        "products": parser.product_data,
        "next_page": parser.next_page,
    }

def scrape_site(start_url, config, use_cloudflare=False):
    all_products = []
    titles = []
    next_url = start_url
    prev_url = None  # keep track of previous page

    while next_url and isinstance(next_url, str):
        print(f"Scraping: {next_url}")

        # Build headers for Cloudflare mode
        headers = {}
        if use_cloudflare and prev_url:
            headers["Referer"] = prev_url

        # Pass headers into scrape_page
        data = scrape_page(next_url, config, use_cloudflare=use_cloudflare, headers=headers)

        all_products.extend(data["products"])
        if not titles and data["titles"]:
            titles = data["titles"]

        prev_url = next_url
        next_url = data["next_page"]

    return {"titles": titles, "products": all_products}


# -------------------------
# Save CSV
# -------------------------
def save_to_csv(products, site_url, product_name):
    domain = urlparse(site_url).netloc.replace("www.", "")
    safe_product = re.sub(r"[^a-zA-Z0-9_-]", "_", product_name.strip())
    filename = f"{domain}-{safe_product}.csv"
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "price", "link"])
        writer.writeheader()
        for product in products:
            writer.writerow(product)
    print(f"\nSaved {len(products)} products to {filename}")

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    SCRAPE_CONFIG = {
        # Basic site (requests only)
        "https://goldspot.com/collections/opus-88": {
            "product": "Opus 88",
            "name": "<a class='boost-pfs-filter-product-item-title'>",
            "link": "<a class='boost-pfs-filter-product-item-title'>",
            "price": "<p class='boost-pfs-filter-product-item-price'>",
            "next": "<a aria-label='Page Next'>",
            "cloudflare": False
        },
        # Cloudflare-protected site
        # "https://www.jetpens.com/search?f=dc76533307a0f275108e40bfb24cc01e&sa=popularity": {
        #     "product": "Opus 88",
        #     "name": "<a class='product-name subtle'>",
        #     "link": "<a class='product-name subtle'>",
        #     "price": "<span class='price'>",
        #     "next": "<a aria-label='Go to next page'>",
        #     "cloudflare": True
        # },
    }

    for url, config in SCRAPE_CONFIG.items():
        data = scrape_site(url, config, use_cloudflare=config.get("cloudflare", False))
        save_to_csv(data["products"], url, config["product"])
