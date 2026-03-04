import pandas as pd
from data_pipeline.scraper.kathmandu import scrape_kathmandupost
from data_pipeline.scraper.setopati import scrape_setopati
from data_pipeline.scraper.onlinekhabar import scrape_onlinekhabar

if __name__ == "__main__":
    print("Scraping")
    data_ktm = scrape_kathmandupost()
    data_seto = scrape_setopati()
    data_online = scrape_onlinekhabar()

    data = data_ktm + data_seto + data_online

    df = pd.DataFrame(data)

    print(df.count())

    df.to_csv("election_news.csv", index=False)

    print("Done! Total articles:", len(df))
