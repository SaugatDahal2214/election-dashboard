import pandas as pd
import re
from collections import defaultdict

# Load data
df = pd.read_csv("election_news.csv")
df["content"] = df["content"].astype(str)
df["title"] = df["title"].astype(str)
df["full_text"] = (df["title"] + " " + df["content"]).str.lower()

# -------------------------
# HELPER FUNCTION
# -------------------------


def contains_any(text, keywords):
    return any(k in text for k in keywords)


# -------------------------
# ENTITY COUNTING
# -------------------------


def count_entities(text):
    counts = defaultdict(int)

    # -----------------
    # KP SHARMA OLI
    # -----------------
    oli_full_patterns = [
        r"\bk\.?\s?p\.?\s?sharma\s?oli\b",
        r"\bkp\s?sharma\s?oli\b",
        r"\bkp\s?sharma\b",
    ]

    for p in oli_full_patterns:
        counts["KP_Oli"] += len(re.findall(p, text))

    # Context-based Oli
    if re.search(r"\boli\b", text):
        if contains_any(text, ["uml", "cpn-uml", "prime minister"]):
            counts["KP_Oli"] += len(re.findall(r"\boli\b", text))

    # -----------------
    # BALEN SHAH
    # -----------------
    balen_patterns = [r"\bbalen\s?shah\b", r"\bbalendra\s?shah\b"]

    for p in balen_patterns:
        counts["Balen_Shah"] += len(re.findall(p, text))

    # Context-based mayor / shah
    if re.search(r"\bbalen\b", text):
        counts["Balen_Shah"] += len(re.findall(r"\bbalen\b", text))

    if re.search(r"\bmayor\b", text):
        if contains_any(text, ["kathmandu", "shah"]):
            counts["Balen_Shah"] += len(re.findall(r"\bmayor\b", text))

    # -----------------
    # GAGAN THAPA
    # -----------------
    gagan_patterns = [r"\bgagan\s?kumar\s?thapa\b", r"\bgagan\s?thapa\b"]

    for p in gagan_patterns:
        counts["Gagan_Thapa"] += len(re.findall(p, text))

    # Context-based thapa
    if re.search(r"\bthapa\b", text):
        if contains_any(text, ["gagan", "nepali congress", "nc"]):
            counts["Gagan_Thapa"] += len(re.findall(r"\bthapa\b", text))

    # -----------------
    # PARTIES
    # -----------------

    # Nepali Congress
    counts["Nepali_Congress"] += len(re.findall(r"\bnepali\s?congress\b", text))
    counts["Nepali_Congress"] += len(re.findall(r"\bnc\b", text))

    # CPN UML
    counts["CPN_UML"] += len(re.findall(r"\bcpn\s?-?\s?uml\b", text))
    counts["CPN_UML"] += len(re.findall(r"\buml\b", text))

    # RSP
    counts["RSP"] += len(re.findall(r"\brastriya\s?swatantra\s?party\b", text))
    counts["RSP"] += len(re.findall(r"\brsp\b", text))

    return dict(counts)


# Apply
df["entity_counts"] = df["full_text"].apply(count_entities)

# Expand columns
entities = ["KP_Oli", "Balen_Shah", "Gagan_Thapa", "Nepali_Congress", "CPN_UML", "RSP"]

for e in entities:
    df[e] = df["entity_counts"].apply(lambda x: x.get(e, 0))

df.to_csv("news_with_clean_tracking.csv", index=False)

# Summary
print("\n=== TOTAL MENTIONS ===")
for e in entities:
    print(e, ":", df[e].sum())
