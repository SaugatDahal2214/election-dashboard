import pandas as pd
from transformers import pipeline
from tqdm import tqdm
import torch

# Detect GPU if available
device = 0 if torch.cuda.is_available() else -1

print("Loading model...")
sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
    device=device,
)

# Load dataset
df = pd.read_csv("election_news.csv")

# Make sure content is string
df["content"] = df["content"].astype(str)


# Function to get sentiment
def get_sentiment(text):
    try:
        result = sentiment_pipeline(text[:512])[0]  # Limit to 512 tokens
        return result["label"], result["score"]
    except:
        return "error", 0.0


tqdm.pandas()

# Apply model
df[["sentiment", "confidence"]] = df["content"].progress_apply(
    lambda x: pd.Series(get_sentiment(x))
)

# Save output
df.to_csv("news_with_sentiment.csv", index=False)

print("Done. File saved as news_with_sentiment.csv")
