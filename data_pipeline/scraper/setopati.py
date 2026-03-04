from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from data_pipeline.scraper.selenium import get_driver

BASE_URL = "https://en.setopati.com/political"
TWO_MONTHS_AGO = datetime.now() - timedelta(days=60)


def extract_article_urls_from_page(driver):
    """
    Extract only article URLs from the main news grid,
    skipping the featured/sticky article at the top.

    Structure:
      section.special-news
        └── div.extra-news-item  ← featured/sticky article (SKIP)
        └── div.row.bishesh.news-cat-list
              └── div.items > a  ← actual paginated articles (KEEP)
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")

    urls = []

    # Only target the paginated grid rows, NOT the featured box at the top
    news_grids = soup.select("div.row.bishesh.news-cat-list")

    for grid in news_grids:
        for item in grid.select("div.items a"):
            href = item.get("href", "")
            if href and "/political/" in href:
                # Ensure it's an article URL (has numeric ID), not a category page
                path = href.rstrip("/").split("/political/")[-1]
                if path.isdigit():
                    urls.append(href)

    return urls


def scrape_article(url):
    """Fetch and parse a single article page."""
    res = requests.get(url, timeout=10)
    if res.status_code != 200:
        print(f"  Failed to fetch {url} (status {res.status_code})")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # Title
    title_tag = soup.select_one("span.news-big-title")
    title = title_tag.get_text(strip=True) if title_tag else "No Title"

    # Date
    published_date_str = ""
    published_date = None
    pub_tag = soup.select_one("span.pub-date")
    if pub_tag:
        pub_text = pub_tag.get_text(strip=True)
        if ":" in pub_text:
            pub_text = pub_text.split(":", 1)[1].strip()
        try:
            published_date = datetime.strptime(pub_text, "%Y-%m-%d %H:%M:%S")
            published_date_str = pub_text
        except ValueError:
            try:
                published_date = datetime.strptime(pub_text, "%Y-%m-%d %H:%M")
                published_date_str = pub_text
            except ValueError:
                print(f"  Could not parse date: '{pub_text}'")
                published_date_str = pub_text

    # Content
    paragraphs = soup.select("div.editor-box p")
    content = "\n".join(
        p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
    )

    return {
        "source": "Setopati",
        "title": title,
        "link": url,
        "content": content,
        "published_date": published_date_str,
        "_parsed_date": published_date,  # used for age check, removed before saving
    }


def scrape_setopati():
    driver = get_driver()
    driver.get(BASE_URL)

    all_data = []
    visited_urls = set()
    page = 1

    while True:
        print(f"\nScraping page {page}...")

        # Wait for the news grid to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.row.bishesh.news-cat-list")
                )
            )
        except TimeoutException:
            print("Timeout waiting for articles.")
            break

        time.sleep(1)  # Let dynamic content settle

        # Extract article URLs from the main grid only (skips featured article at top)
        page_urls = extract_article_urls_from_page(driver)

        # Filter out already-visited URLs
        new_urls = [u for u in page_urls if u not in visited_urls]

        print(
            f"  Total grid URLs: {len(page_urls)} | "
            f"New: {len(new_urls)} | "
            f"Already visited: {len(page_urls) - len(new_urls)}"
        )

        if not new_urls:
            print("  No new articles on this page. Stopping.")
            break

        stop_after_page = False

        for url in new_urls:
            visited_urls.add(url)
            print(f"  Opening: {url}")

            try:
                article = scrape_article(url)
                if article is None:
                    continue

                parsed_date = article.pop("_parsed_date")

                if parsed_date and parsed_date < TWO_MONTHS_AGO:
                    print(
                        f"  Article older than 2 months ({article['published_date']}). "
                        "Will stop after this page."
                    )
                    stop_after_page = True
                    # Don't save articles older than 2 months
                else:
                    all_data.append(article)
                    print(f"  Saved: {article['title']}")

            except Exception as e:
                print(f"  Error processing {url}: {e}")
                continue

        if stop_after_page:
            print("Stopping — reached articles older than 2 months.")
            break

        # Pagination: use rel="next" to avoid matching "Previous" button
        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.nextpostslink[rel='next']")
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
