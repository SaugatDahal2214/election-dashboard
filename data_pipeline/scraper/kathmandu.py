from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time

from data_pipeline.scraper.selenium import get_driver
from data_pipeline.common_utils import is_recent, contains_election_keywords

BASE_URL = "https://kathmandupost.com/politics"
TWO_MONTHS_AGO = datetime.now() - timedelta(days=60)


def scrape_kathmandupost():
    driver = get_driver()
    articles_data = []

    try:
        driver.get(BASE_URL)

        wait = WebDriverWait(driver, 15)

        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#news-list article.article-image")
            )
        )

        load_more_rounds = 0

        while True:
            try:
                load_more = wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "load-more-btn"))
                )
                driver.execute_script("arguments[0].click();", load_more)
                time.sleep(2)
                load_more_rounds += 1
                print(f"Clicked Load More {load_more_rounds} times")

                if load_more_rounds >= 10:
                    break

            except:
                print("No more Load More button")
                break

        h3_elements = driver.find_elements(
            By.CSS_SELECTOR, "#news-list article.article-image h3"
        )

        urls = []
        for h3 in h3_elements:
            try:
                parent_a = h3.find_element(By.XPATH, "..")
                link = parent_a.get_attribute("href")
                if link and link not in urls:
                    urls.append(link)
            except:
                continue

        print(f"Collected {len(urls)} URLs")

        for url in urls:
            try:
                driver.get(url)

                title_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.col-sm-8 h1"))
                )
                title = title_element.text.strip()

                date_elem = driver.find_element(By.CLASS_NAME, "updated-time")
                raw_text = date_elem.text

                date_part = raw_text.split("Published at :")[-1].strip()

                published_date = datetime.strptime(date_part, "%B %d, %Y")
                if published_date < TWO_MONTHS_AGO:
                    print("Reached older than 2 months. Stopping.")
                    break

                paragraphs = driver.find_elements(
                    By.CSS_SELECTOR, "section.story-section p"
                )

                content = "\n".join(
                    p.text.strip() for p in paragraphs if p.text.strip()
                )

                # Keyword filter
                if not contains_election_keywords(content + " " + title):
                    continue

                articles_data.append(
                    {
                        "source": "Kathmandu Post",
                        "title": title,
                        "link": url,
                        "content": content,
                        "published_date": published_date,
                    }
                )

                print(f"✔ Scraped: {title}")

            except Exception as e:
                print(f"Failed to scrape {url}: {e}")
                continue

    finally:
        driver.quit()

    return articles_data
