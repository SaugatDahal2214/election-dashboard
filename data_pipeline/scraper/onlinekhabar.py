from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from data_pipeline.scraper.selenium import get_driver

BASE_URL = "https://english.onlinekhabar.com/category/political"
TWO_MONTHS_AGO = datetime.now() - timedelta(days=60)


def extract_article_urls_from_page(driver):
    """
    Extract article URLs from the main news listing grid.

    Structure:
      div.ok-news-post.ltr-post
        └── a.ok-post-image  ← article link
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")
    urls = []
    for post in soup.select("div.ok-news-post.ltr-post"):
        link = post.select_one("a.ok-post-image")
        if not link:
            continue
        href = link.get("href", "").strip()
        if href and href.startswith("https://english.onlinekhabar.com/"):
            urls.append(href)
    return urls


def parse_date(soup):
    """
    Try multiple selectors and formats to extract the published date.
    Returns (datetime | None, str)
    """
    # Most reliable: Open Graph / schema meta tags always have the full ISO date
    for meta_prop in ["article:published_time", "datePublished"]:
        meta = (
            soup.select_one(f'meta[property="{meta_prop}"]')
            or soup.select_one(f'meta[name="{meta_prop}"]')
            or soup.select_one(f'[itemprop="{meta_prop}"]')
        )
        if meta:
            raw = (
                meta.get("content", "")
                or meta.get("datetime", "")
                or meta.get_text(strip=True)
            )
            normalised = raw[:19].replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(normalised, fmt)
                    return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

    candidates = [
        soup.select_one("time.ok-post-published-date"),
        soup.select_one("time[datetime]"),
        soup.select_one("time"),
        soup.select_one("span.ok-post-date"),
        soup.select_one("span.date"),
    ]

    for tag in candidates:
        if tag is None:
            continue

        # Prefer the datetime attribute, fall back to text
        raw = tag.get("datetime", "").strip() or tag.get_text(strip=True)
        if not raw:
            continue

        # Normalise: strip timezone offset (+05:45 etc.) and trailing decimals
        normalised = raw[:19].replace("T", " ")

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(normalised, fmt)
                return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

    # Fallback: plain text date like "Tuesday, December 23, 2025" or "December 23, 2025"
    plain = soup.get_text(" ", strip=True) if hasattr(soup, "get_text") else ""
    # Also check common author/date wrapper tags directly
    for tag in [
        soup.select_one("span.ok-post-date"),
        soup.select_one("div.ok-single-post-meta span"),
        soup.select_one("p.ok-post-meta"),
        soup.select_one("div.post-infos span"),
    ]:
        if tag is None:
            continue
        raw = tag.get_text(strip=True)
        for fmt in ("%A, %B %d, %Y", "%B %d, %Y", "%A, %b %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

    return None, ""


def scrape_article(url):
    """Fetch and parse a single article page."""
    res = requests.get(url, timeout=10)
    if res.status_code != 200:
        print(f"  Failed to fetch {url} (status {res.status_code})")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # Title
    title_tag = soup.select_one("h1.ok-single-post-title") or soup.select_one("h1")
    title = title_tag.get_text(strip=True) if title_tag else "No Title"

    # Date — parsed from the article page itself (listing only has relative times)
    published_date, published_date_str = parse_date(soup)
    if not published_date:
        print(f"  Could not parse date for: {url}")

    # Content
    paragraphs = soup.select("div.ok-single-post-content p")
    content = "\n".join(
        p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
    )

    return {
        "source": "OnlineKhabar",
        "title": title,
        "link": url,
        "content": content,
        "published_date": published_date_str,
        "_parsed_date": published_date,  # used for age check, removed before saving
    }


def scrape_onlinekhabar():
    driver = get_driver()
    driver.get(BASE_URL)

    all_data = []
    visited_urls = set()
    page = 1
    stop_scraping = False  # flag set as soon as one old article is found

    while True:
        print(f"\nScraping page {page}...")

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.ok-news-post.ltr-post")
                )
            )
        except TimeoutException:
            print("Timeout waiting for articles.")
            break

        time.sleep(1)

        page_urls = extract_article_urls_from_page(driver)
        new_urls = [u for u in page_urls if u not in visited_urls]

        print(
            f"  Total grid URLs: {len(page_urls)} | "
            f"New: {len(new_urls)} | "
            f"Already visited: {len(page_urls) - len(new_urls)}"
        )

        if not new_urls:
            print("  No new articles on this page. Stopping.")
            break

        for url in new_urls:
            visited_urls.add(url)
            print(f"  Opening: {url}")

            try:
                article = scrape_article(url)
                if article is None:
                    continue

                parsed_date = article.pop("_parsed_date")

                # If date is unknown, save the article and keep going
                if parsed_date and parsed_date < TWO_MONTHS_AGO:
                    print(
                        f"  Article older than 2 months ({article['published_date']}). "
                        "Stopping immediately."
                    )
                    stop_scraping = True
                    break  # ← stop processing remaining URLs on this page immediately

                all_data.append(article)
                print(f"  Saved: {article['title']}")

            except Exception as e:
                print(f"  Error processing {url}: {e}")
                continue

        if stop_scraping:
            print("Stopping — reached articles older than 2 months.")
            break

        # Pagination
        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.next.page-numbers")
                )
            )
            next_button.click()
            page += 1
            time.sleep(2)
        except TimeoutException:
            print("No more pages.")
            break
        except Exception as e:
            print(f"Pagination error: {e}")
            break

    driver.quit()
    print(f"\nDone! Total articles scraped: {len(all_data)}")
    return all_data