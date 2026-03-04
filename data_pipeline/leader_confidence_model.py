import pandas as pd
import re
from transformers import pipeline
import torch
from collections import defaultdict
from datetime import timedelta

# -----------------------
# LOAD DATA
# -----------------------
df = pd.read_csv("news_with_clean_tracking.csv")

df["title"] = df["title"].fillna("").astype(str)
df["content"] = df["content"].fillna("").astype(str)
df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
df = df.dropna(subset=["published_date"])

# -----------------------
# DATE WINDOWS
# -----------------------
max_date = df["published_date"].max()
recent_cutoff = max_date - timedelta(days=30)
previous_cutoff = max_date - timedelta(days=60)

recent_df = df[df["published_date"] >= recent_cutoff]
previous_df = df[
    (df["published_date"] < recent_cutoff) & (df["published_date"] >= previous_cutoff)
]

# -----------------------
# SENTIMENT MODEL
# -----------------------
device = 0 if torch.cuda.is_available() else -1

sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
    device=device,
)

# -----------------------
# LEADER PATTERNS
# -----------------------
leaders = {
    "KP_Oli": r"\boli\b|\bkp\b",
    "Balen_Shah": r"\bbalen\b|\bshah\b",
    "Gagan_Thapa": r"\bgagan\b|\bthapa\b",
}


# -----------------------
# HELPER FUNCTION
# -----------------------
def extract_sentiments(dataframe, pattern):
    sentiments = []

    for _, row in dataframe.iterrows():
        text = (row["title"] + " " + row["content"]).lower()
        sentences = re.split(r"[.!?]", text)

        for sentence in sentences:
            if re.search(pattern, sentence):
                result = sentiment_pipeline(sentence[:512])[0]
                sentiments.append(result["label"])

    return sentiments


# -----------------------
# COMPUTE METRICS
# -----------------------
results = {}
all_mentions = 0
mention_counts = {}

# First pass: total mentions
for leader, pattern in leaders.items():
    sentiments = extract_sentiments(df, pattern)
    mention_counts[leader] = len(sentiments)
    all_mentions += len(sentiments)

# Second pass: compute scores
for leader, pattern in leaders.items():

    # Full sentiment
    full_sentiments = extract_sentiments(df, pattern)
    total = len(full_sentiments)

    if total == 0:
        results[leader] = 0
        continue

    pos = full_sentiments.count("positive")
    neg = full_sentiments.count("negative")
    S = (pos - neg) / total

    # Volume
    V = mention_counts[leader] / all_mentions if all_mentions != 0 else 0

    # Momentum
    recent_sent = extract_sentiments(recent_df, pattern)
    previous_sent = extract_sentiments(previous_df, pattern)

    if len(recent_sent) > 0:
        recent_S = (
            recent_sent.count("positive") - recent_sent.count("negative")
        ) / len(recent_sent)
    else:
        recent_S = 0

    if len(previous_sent) > 0:
        previous_S = (
            previous_sent.count("positive") - previous_sent.count("negative")
        ) / len(previous_sent)
    else:
        previous_S = 0

    M = recent_S - previous_S

    # Final MCI v2
    MCI_v2 = 0.4 * S + 0.3 * V + 0.3 * M

    results[leader] = {
        "Sentiment_Score": round(S, 3),
        "Volume_Score": round(V, 3),
        "Momentum": round(M, 3),
        "MCI_v2": round(MCI_v2, 3),
        "Total_Mentions": total,
    }

# -----------------------
# OUTPUT
# -----------------------
print("\n=== MEDIA CONFIDENCE INDEX v2 ===")
for leader, metrics in results.items():
    print(leader, metrics)

results_df = pd.DataFrame(results).T
results_df.reset_index(inplace=True)
results_df.rename(columns={"index": "Leader"}, inplace=True)
results_df.to_csv("leader_mci_v2_results.csv", index=False)
