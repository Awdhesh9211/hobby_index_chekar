import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

DOMAIN = "https://sphereglobal.solutions"
SITEMAP_URL = f"{DOMAIN}/sitemap.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SEOIndexChecker/1.0)"
}


def get_sitemap_urls(sitemap_url):
    """Get URLs from sitemap.xml"""

    print(f"\nReading sitemap: {sitemap_url}")

    try:
        response = requests.get(
            sitemap_url,
            headers=HEADERS,
            timeout=20
        )

        print(f"Sitemap status: {response.status_code}")

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "xml")

        # Normal sitemap
        urls = [
            loc.get_text(strip=True)
            for loc in soup.find_all("loc")
        ]

        return urls

    except requests.RequestException as e:
        print(f"Sitemap error: {e}")
        return []


def check_url(url):
    """Check URL HTTP status and meta robots"""

    result = {
        "url": url,
        "status_code": "",
        "accessible": False,
        "robots_meta": "",
        "noindex": False,
        "canonical": "",
        "error": ""
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True
        )

        result["status_code"] = response.status_code
        result["accessible"] = response.status_code == 200

        soup = BeautifulSoup(response.text, "html.parser")

        # Check meta robots
        robots = soup.find(
            "meta",
            attrs={"name": lambda x: x and x.lower() == "robots"}
        )

        if robots:
            content = robots.get("content", "").strip()
            result["robots_meta"] = content

            if "noindex" in content.lower():
                result["noindex"] = True

        # Check canonical
        canonical = soup.find(
            "link",
            rel=lambda x: x and "canonical" in x
        )

        if canonical:
            result["canonical"] = canonical.get("href", "")

        # Show redirect destination if different
        if response.url != url:
            result["final_url"] = response.url
        else:
            result["final_url"] = url

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def main():

    print("=" * 70)
    print("SEO INDEXABILITY CHECKER")
    print("=" * 70)

    # --------------------------------------------------
    # 1. Get sitemap URLs
    # --------------------------------------------------

    urls = get_sitemap_urls(SITEMAP_URL)

    if not urls:
        print("\nNo URLs found in sitemap.")
        return

    print(f"\nTotal URLs found: {len(urls)}")

    # Remove duplicates
    urls = list(dict.fromkeys(urls))

    print(f"Unique URLs: {len(urls)}")

    # --------------------------------------------------
    # 2. Check URLs
    # --------------------------------------------------

    results = []

    for index, url in enumerate(urls, start=1):

        print(
            f"[{index}/{len(urls)}] Checking: {url}"
        )

        result = check_url(url)
        results.append(result)

        # Don't hammer server
        time.sleep(0.5)

    # --------------------------------------------------
    # 3. Save CSV
    # --------------------------------------------------

    df = pd.DataFrame(results)

    output_file = "seo_indexability_report.csv"

    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------
    # 4. Summary
    # --------------------------------------------------

    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total = len(df)

    status_200 = len(
        df[df["status_code"] == 200]
    )

    noindex = len(
        df[df["noindex"] == True]
    )

    errors = len(
        df[df["error"] != ""]
    )

    print(f"Total URLs       : {total}")
    print(f"HTTP 200         : {status_200}")
    print(f"Noindex pages    : {noindex}")
    print(f"Errors           : {errors}")

    print("\nReport saved as:")
    print(output_file)


if __name__ == "__main__":
    main()