# **WebScrape**

A lightweight Python web scraper that supports both normal websites and Cloudflare-protected sites (via cloudscraper).\
It extracts product names, links, and prices from e-commerce sites and saves them to CSV files.

## Installation:

1. Create a Python virtual environment

   - Open a bash or cmd shell and create a Python virtual environment "ws" (Python 3.12+ recommended)

```bash
python3 -m venv ws
```

2. Activate Python virtual environment
   - On Linux / macOS:

```bash
$ cd ws
$ source venv/bin/activate
```
   - On Windows (cmd.exe):

```cmd.exe
cd ws
.\venv\Scripts\activate
```

3. Clone the repository

```bash
$ git clone git@github.com:st9635/webscrape.git
$ cd webscrape
```

4. Install dependencies
```bash
$ pip install -r requirements.txt
```

## Usage:

1. Run the scraper (python3 or python command):

```bash
$ python3 ws10.py
```

2. Configure what to scrape
   - Open the script and edit the SCRAPE_CONFIG dictionary at the bottom:

```python
SCRAPE_CONFIG = {
    # Example: normal site (basic requests)
    "https://goldspot.com/collections/opus-88": {
        "product": "Opus 88",
        "name": "<a class='boost-pfs-filter-product-item-title'>",
        "link": "<a class='boost-pfs-filter-product-item-title'>",
        "price": "<p class='boost-pfs-filter-product-item-price'>",
        "next": "<a aria-label='Page Next'>",
        "cloudflare": False
    },
    # Example: Cloudflare-protected site (use cloudscraper)
    "https://www.jetpens.com/search?f=...&sa=popularity": {
        "product": "Opus 88",
        "name": "<a class='product-name subtle'>",
        "link": "<a class='product-name subtle'>",
        "price": "<span class='price'>",
        "next": "<a aria-label='Go to next page'>",
        "cloudflare": True
    },
}
```
> + product → label used for the output filename.
> + name / link / price → HTML tags or selectors for scraping.
> + next → selector for the pagination link.
> + cloudflare → set to True for Cloudflare-protected sites, False otherwise.


3. Output

For each configured site, a CSV file will be saved automatically in the project folder.\
> Format: \<domain>-\<product>.csv\
> Example: goldspot.com-Opus_88.csv

4. Columns:

> name – product name\
> price – product price\
> link – product link\


**Notes**

+ In auto-detect mode (use_cloudflare=None), the scraper will first try requests and automatically fall back to cloudscraper if a Cloudflare block is detected.

+ Pagination is followed automatically, and Referer headers are injected when scraping Cloudflare-protected sites to avoid 403 errors.

+ Some sites may require fine-tuning of tag selectors in SCRAPE_CONFIG.