import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# === Zapier Webhook URL ===
ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/24642020/um0pk5v/"  # Replace with your Zapier URL

def send_to_zapier(data):
    """Send scraped data to Zapier webhook"""
    try:
        response = requests.post(ZAPIER_WEBHOOK_URL, json=data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Sent {data.get('Phone Name')} to Zapier")
        else:
            print(f"❌ Failed to send data: {response.text}")
    except Exception as e:
        print(f"❌ Error sending to Zapier: {e}")



# === Config ===
BASE_URL = "https://www.gsmarena.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
LIMIT_PRODUCTS = 30   # ✅ scrape only first 5 products


def fetch_html(url):
    """Fetch page content with retries."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return ""


def get_product_urls(listing_html):
    """Extract product URLs from search results page."""
    soup = BeautifulSoup(listing_html, "html.parser")
    urls = []
    for li in soup.select("div#review-body ul li a"):
        href = li.get("href", "")
        if href:
            urls.append(BASE_URL + href)
    return urls


def extract_key_specs(soup):
    specs_ul = soup.find("ul", class_="specs-spotlight-features")
    if not specs_ul:
        return {}

    def get_data_spec(attr):
        el = specs_ul.find(attrs={"data-spec": attr})
        return el.text.strip() if el else ""

    return {
        "Released": get_data_spec("released-hl"),
        "Body": get_data_spec("body-hl"),
        "OS": get_data_spec("os-hl"),
        "Storage": get_data_spec("storage-hl"),
        "Display Size": get_data_spec("displaysize-hl"),
        "Display Resolution": get_data_spec("displayres-hl"),
        "Camera (MP)": get_data_spec("camerapixels-hl"),
        "Video": get_data_spec("videopixels-hl"),
        "RAM (GB)": get_data_spec("ramsize-hl"),
        "Chipset": get_data_spec("chipset-hl"),
        "Battery (mAh)": get_data_spec("batsize-hl"),
        "Charging": get_data_spec("battype-hl")
    }


def extract_full_specs(soup):
    specs_div = soup.find("div", id="specs-list")
    if not specs_div:
        return {}

    full_specs = {}
    for table in specs_div.find_all("table"):
        category = None
        rows = table.find_all("tr")
        for row in rows:
            th = row.find("th")
            if th:
                category = th.get_text(strip=True)
                full_specs[category] = {}
            tds = row.find_all("td")
            if len(tds) == 2 and category:
                label = tds[0].get_text(strip=True)
                value = tds[1].get_text(" ", strip=True)
                full_specs[category][label] = value
    return full_specs


def combine_full_specs_sectionwise(specs_dict):
    flat = {}
    for section, items in specs_dict.items():
        lines = [f"{k}: {v}" for k, v in items.items()]
        flat[section] = " | ".join(lines)
    return flat


def get_price_page_url(soup):
    tag = soup.select_one("li.article-info-meta-link a[href*='-price']")
    if tag:
        href = tag.get("href", "")
        return BASE_URL + href
    return ""


def extract_price_info(price_html):
    soup = BeautifulSoup(price_html, "html.parser")
    platforms, prices = [], []

    for table in soup.select("table.pricing"):
        location = table.find("caption")
        location_text = location.get_text(strip=True) if location else "Unknown Location"

        thead = table.find("thead")
        if not thead:
            continue

        variant_headers = [th.get_text(strip=True) for th in thead.find_all("th")][1:]

        tbody = table.find("tbody")
        if not tbody:
            continue

        for row in tbody.find_all("tr"):
            img = row.find("img")
            platform_name = img.get("alt", "").strip() if img else "Unknown Platform"
            cells = row.find_all("td")

            for idx, cell in enumerate(cells):
                variant = variant_headers[idx] if idx < len(variant_headers) else f"Variant {idx+1}"
                price = cell.get_text(strip=True)

                label = f"{location_text} - {variant} - {platform_name}"
                platforms.append(label)
                prices.append(price)

    return {
        "Price Platforms": "\n".join(platforms),
        "Price Values": "\n".join(prices)
    }


def main():
    all_data = []

    # ✅ Use the search results page
    listing_url = "https://www.gsmarena.com/results.php3?nYearMin=2025"
    print(f"📄 Scraping listing: {listing_url}")
    listing_html = fetch_html(listing_url)
    if not listing_html:
        return

    product_urls = get_product_urls(listing_html)

    # ✅ Limit to first N products
    product_urls = product_urls[:LIMIT_PRODUCTS]

    for idx, product_url in enumerate(product_urls, start=1):
        print(f"🔍 ({idx}/{len(product_urls)}) Scraping product: {product_url}")
        html = fetch_html(product_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        phone_name = soup.find("h1").text.strip() if soup.find("h1") else "Unknown"
        key_specs = extract_key_specs(soup)
        full_specs = extract_full_specs(soup)
        flat_full_specs = combine_full_specs_sectionwise(full_specs)

        price_url = get_price_page_url(soup)
        price_data = {}
        if price_url:
            print(f"💲 Fetching price from: {price_url}")
            price_html = fetch_html(price_url)
            price_data = extract_price_info(price_html)
        else:
            print("⚠️ No price link found.")

        combined = {
            "Phone Name": phone_name,
            **key_specs,
            **flat_full_specs,
            **price_data,
            "Product URL": product_url,
            "Price Page URL": price_url if price_url else "N/A"
        }

        all_data.append(combined)

        # 🔗 Send each product to Zapier
        send_to_zapier(combined)

        time.sleep(2)

    df = pd.DataFrame(all_data)

    # Save as .xlsx to avoid auto-formatting in Excel
    output_filename = "gsmarena_2025_first5_products.xlsx"
    with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)

    print(f"✅ Data saved to {output_filename}")



if __name__ == "__main__":
    main()
