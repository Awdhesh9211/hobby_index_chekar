import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="SEO Indexability Checker",
    page_icon="🔎",
    layout="wide"
)

# --------------------------------------------------
# Constants
# --------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20


# --------------------------------------------------
# Normalize Domain
# --------------------------------------------------

def normalize_domain(domain):
    domain = domain.strip()

    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain

    return domain.rstrip("/")


# --------------------------------------------------
# Fetch Sitemap
# --------------------------------------------------

def get_sitemap_urls(sitemap_url):
    """
    Fetch sitemap.xml and extract URLs.

    Supports:
    - Normal sitemap
    - Sitemap index
    """

    response = requests.get(
        sitemap_url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.content,
        "xml"
    )

    # Check if this is a sitemap index
    sitemap_tags = soup.find_all("sitemap")

    if sitemap_tags:
        all_urls = []

        for sitemap in sitemap_tags:
            loc = sitemap.find("loc")

            if loc:
                child_sitemap = loc.get_text(strip=True)

                try:
                    child_urls = get_sitemap_urls(
                        child_sitemap
                    )

                    all_urls.extend(child_urls)

                except Exception as e:
                    st.warning(
                        f"Could not read sitemap: {child_sitemap} "
                        f"({e})"
                    )

        return list(dict.fromkeys(all_urls))

    # Normal sitemap
    url_tags = soup.find_all("url")

    urls = []

    for url_tag in url_tags:
        loc = url_tag.find("loc")

        if loc:
            urls.append(
                loc.get_text(strip=True)
            )

    return list(dict.fromkeys(urls))


# --------------------------------------------------
# Check robots.txt
# --------------------------------------------------

def get_robots_status(domain):
    robots_url = urljoin(
        domain + "/",
        "robots.txt"
    )

    try:
        response = requests.get(
            robots_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return True, response.text

        return False, ""

    except Exception:
        return False, ""


# --------------------------------------------------
# Check URL
# --------------------------------------------------

def check_url(url):
    result = {
        "URL": url,
        "Status": "",
        "Indexable": "",
        "HTTP Status": "",
        "Meta Robots": "",
        "X-Robots-Tag": "",
        "Canonical": "",
        "Final URL": "",
        "Reason": ""
    }

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        result["HTTP Status"] = response.status_code
        result["Final URL"] = response.url

        # --------------------------------------------------
        # HTTP status
        # --------------------------------------------------

        if response.status_code != 200:

            result["Status"] = "❌ Not Indexable"
            result["Indexable"] = False
            result["Reason"] = (
                f"HTTP status {response.status_code}"
            )

            return result

        # --------------------------------------------------
        # Parse HTML
        # --------------------------------------------------

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # --------------------------------------------------
        # Meta Robots
        # --------------------------------------------------

        robots_tag = soup.find(
            "meta",
            attrs={
                "name": lambda value:
                value and value.lower() == "robots"
            }
        )

        meta_robots = ""

        if robots_tag:
            meta_robots = robots_tag.get(
                "content",
                ""
            ).strip()

        result["Meta Robots"] = meta_robots

        # --------------------------------------------------
        # X-Robots-Tag
        # --------------------------------------------------

        x_robots = response.headers.get(
            "X-Robots-Tag",
            ""
        )

        result["X-Robots-Tag"] = x_robots

        # --------------------------------------------------
        # Canonical
        # --------------------------------------------------

        canonical_tag = soup.find(
            "link",
            rel=lambda value:
            value and "canonical" in value
        )

        if canonical_tag:
            result["Canonical"] = canonical_tag.get(
                "href",
                ""
            )

        # --------------------------------------------------
        # Check noindex
        # --------------------------------------------------

        meta_noindex = (
            "noindex" in meta_robots.lower()
        )

        header_noindex = (
            "noindex" in x_robots.lower()
        )

        # --------------------------------------------------
        # Final decision
        # --------------------------------------------------

        if meta_noindex:

            result["Status"] = "❌ Not Indexable"
            result["Indexable"] = False
            result["Reason"] = (
                "meta robots contains noindex"
            )

        elif header_noindex:

            result["Status"] = "❌ Not Indexable"
            result["Indexable"] = False
            result["Reason"] = (
                "X-Robots-Tag contains noindex"
            )

        else:

            result["Status"] = "✅ Indexable"
            result["Indexable"] = True
            result["Reason"] = (
                "HTTP 200 and no noindex directive detected"
            )

    except requests.exceptions.Timeout:

        result["Status"] = "⚠️ Error"
        result["Indexable"] = False
        result["Reason"] = "Request timeout"

    except requests.exceptions.RequestException as e:

        result["Status"] = "⚠️ Error"
        result["Indexable"] = False
        result["Reason"] = str(e)

    except Exception as e:

        result["Status"] = "⚠️ Error"
        result["Indexable"] = False
        result["Reason"] = str(e)

    return result


# --------------------------------------------------
# Main App
# --------------------------------------------------

st.title("🔎 SEO Indexability Checker")

st.caption(
    "Check sitemap URLs for technical indexability signals."
)

# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:

    st.header("Website")

    domain = st.text_input(
        "Domain",
        value="https://sphereglobal.solutions"
    )

    max_workers = st.slider(
        "Concurrent requests",
        min_value=1,
        max_value=20,
        value=8
    )

    st.info(
        "This tool checks technical indexability. "
        "It does not confirm whether Google has actually "
        "indexed the URL."
    )


# --------------------------------------------------
# Start Scan
# --------------------------------------------------

if st.button(
    "🚀 Start SEO Scan",
    type="primary",
    use_container_width=True
):

    domain = normalize_domain(domain)

    parsed = urlparse(domain)

    if not parsed.netloc:

        st.error("Please enter a valid domain.")

        st.stop()

    sitemap_url = urljoin(
        domain + "/",
        "sitemap.xml"
    )

    # --------------------------------------------------
    # Robots
    # --------------------------------------------------

    with st.spinner("Checking robots.txt..."):

        robots_exists, robots_content = (
            get_robots_status(domain)
        )

    if robots_exists:
        st.success("✅ robots.txt found")
    else:
        st.warning("⚠️ robots.txt not found")

    # --------------------------------------------------
    # Sitemap
    # --------------------------------------------------

    st.info(
        f"Reading sitemap: `{sitemap_url}`"
    )

    try:

        with st.spinner(
            "Fetching sitemap URLs..."
        ):

            urls = get_sitemap_urls(
                sitemap_url
            )

    except Exception as e:

        st.error(
            f"Could not read sitemap: {e}"
        )

        st.stop()

    if not urls:

        st.warning(
            "No URLs found in sitemap."
        )

        st.stop()

    st.success(
        f"Found {len(urls)} URLs"
    )

    # --------------------------------------------------
    # Progress
    # --------------------------------------------------

    progress = st.progress(0)

    status_text = st.empty()

    results = []

    total = len(urls)

    # --------------------------------------------------
    # Concurrent URL checking
    # --------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        futures = {
            executor.submit(
                check_url,
                url
            ): url
            for url in urls
        }

        completed = 0

        for future in as_completed(
            futures
        ):

            try:

                result = future.result()
                results.append(result)

            except Exception as e:

                results.append({
                    "URL": futures[future],
                    "Status": "⚠️ Error",
                    "Indexable": False,
                    "HTTP Status": "",
                    "Meta Robots": "",
                    "X-Robots-Tag": "",
                    "Canonical": "",
                    "Final URL": "",
                    "Reason": str(e)
                })

            completed += 1

            progress_value = (
                completed / total
            )

            progress.progress(
                progress_value
            )

            status_text.write(
                f"Checking URLs: "
                f"{completed}/{total}"
            )

    # --------------------------------------------------
    # DataFrame
    # --------------------------------------------------

    df = pd.DataFrame(results)

    # Keep sitemap order
    url_order = {
        url: index
        for index, url in enumerate(urls)
    }

    df["_order"] = df["URL"].map(
        url_order
    )

    df = df.sort_values(
        "_order"
    ).drop(
        columns=["_order"]
    )

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    indexable_count = len(
        df[df["Indexable"] == True]
    )

    not_indexable_count = len(
        df[df["Indexable"] == False]
    )

    error_count = len(
        df[df["Status"] == "⚠️ Error"]
    )

    # --------------------------------------------------
    # Metrics
    # --------------------------------------------------

    st.subheader("📊 Scan Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total URLs",
        len(df)
    )

    col2.metric(
        "✅ Indexable",
        indexable_count
    )

    col3.metric(
        "❌ Not Indexable",
        not_indexable_count
    )

    col4.metric(
        "⚠️ Errors",
        error_count
    )

    # --------------------------------------------------
    # Filters
    # --------------------------------------------------

    st.subheader("📋 URL Results")

    filter_option = st.selectbox(
        "Filter",
        [
            "All",
            "✅ Indexable",
            "❌ Not Indexable",
            "⚠️ Error"
        ]
    )

    if filter_option != "All":

        filtered_df = df[
            df["Status"] == filter_option
        ]

    else:

        filtered_df = df

    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=600
    )

    # --------------------------------------------------
    # Download CSV
    # --------------------------------------------------

    csv = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download CSV Report",
        data=csv,
        file_name="seo_indexability_report.csv",
        mime="text/csv",
        use_container_width=True
    )

    # --------------------------------------------------
    # Noindex URLs
    # --------------------------------------------------

    noindex_df = df[
        df["Status"] == "❌ Not Indexable"
    ]

    if not noindex_df.empty:

        st.subheader(
            "❌ Not Indexable URLs"
        )

        st.dataframe(
            noindex_df[
                [
                    "URL",
                    "HTTP Status",
                    "Meta Robots",
                    "X-Robots-Tag",
                    "Reason"
                ]
            ],
            use_container_width=True
        )