import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from datetime import timedelta

st.set_page_config(page_title="Election Media Confidence Dashboard", layout="wide")
st.title("📊 Media Confidence Index Dashboard (Nepal Election 2082)")

st.markdown(
    """
**This dashboard visualizes the media confidence of leaders and parties** based on news sentiment, coverage, and trends from the past 2 months collected from three major news portals: **Kathmandu Post, Setopati, and OnlineKhabar**.

**Metrics Explained:**
- **Sentiment Score**: Indicates whether media coverage is positive or negative about a leader or party. Higher is better.
- **Volume Score**: Measures how frequently a leader or party is mentioned. Higher means more coverage.
- **Momentum**: Shows if media narrative is rising (positive) or declining (negative) compared to the previous month.
- **MCI v2**: Overall confidence score combining Sentiment, Volume, and Momentum. Higher indicates stronger media confidence.
- **Scenario Simulator**: Use sliders to adjust the influence of Sentiment, Volume, and Momentum and see how the overall scores change.
"""
)

# -----------------------
# Load Data
# -----------------------
leaders_df = pd.read_csv("data_pipeline/leader_mci_v2_results.csv")
parties_df = pd.read_csv("data_pipeline/party_mci_v2_results.csv")
news_df = pd.read_csv("news_with_clean_tracking.csv")

news_df["published_date"] = pd.to_datetime(news_df["published_date"], errors="coerce")
news_df = news_df.dropna(subset=["published_date"])
news_df["title"] = news_df["title"].fillna("").astype(str)
news_df["content"] = news_df["content"].fillna("").astype(str)
news_df["date"] = news_df["published_date"].dt.date

# -----------------------
# Leader / Party Variants
# -----------------------
leader_patterns = {
    "KP_Oli": ["kp oli", "kp", "kp sharma oli", "kp sharma"],
    "Balen_Shah": ["balen shah", "balen", "mayor", "shah", "balendra"],
    "Gagan_Thapa": ["gagan thapa", "gagan kumar thapa", "gagan", "thapa"],
}

party_patterns = {
    "CPN_UML": ["cpn uml", "uml"],
    "Nepali_Congress": ["nepali congress", "nc"],
    "RSP": ["rastriya swatantra party", "rsp"],
}

# -----------------------
# View Toggle
# -----------------------
view_option = st.sidebar.radio("View Mode", ["Leaders", "Parties"])
if view_option == "Leaders":
    df = leaders_df.copy()
    df["Name"] = df["Leader"]
    patterns_dict = leader_patterns
else:
    df = parties_df.copy()
    df["Name"] = df["Party"]
    patterns_dict = party_patterns

# -----------------------
# Scenario Simulator
# -----------------------
st.sidebar.header("⚙ Scenario Simulator")
st.sidebar.markdown(
    """
Adjust the sliders to change how **Sentiment**, **Volume**, and **Momentum** affect the overall media confidence score (MCI v2).

- Increase **Sentiment Weight** → positive news has more impact.
- Increase **Volume Weight** → heavily covered figures rise in score.
- Increase **Momentum Weight** → rising narratives get more influence.
"""
)
sentiment_weight = st.sidebar.slider("Sentiment Weight", 0.0, 1.0, 0.4)
volume_weight = st.sidebar.slider("Volume Weight", 0.0, 1.0, 0.3)
momentum_weight = st.sidebar.slider("Momentum Weight", 0.0, 1.0, 0.3)

# Normalize
total_weight = sentiment_weight + volume_weight + momentum_weight
sentiment_weight /= total_weight
volume_weight /= total_weight
momentum_weight /= total_weight

df["Scenario_Score"] = (
    sentiment_weight * df["Sentiment_Score"]
    + volume_weight * df["Volume_Score"]
    + momentum_weight * df["Momentum"]
)
df = df.round(3)

# -----------------------
# Ranking Bar Chart
# -----------------------
st.subheader(f"🏆 {view_option} Ranking (Scenario Adjusted)")
st.markdown(
    "Shows overall ranking based on your chosen weights. Higher bars mean stronger media confidence."
)

rank_fig = px.bar(
    df.sort_values("Scenario_Score", ascending=False),
    x="Name",
    y="Scenario_Score",
    text="Scenario_Score",
    color="Scenario_Score",
    color_continuous_scale="Blues",
)
st.plotly_chart(rank_fig, use_container_width=True)

# -----------------------
# Momentum Trend Arrows
# -----------------------
st.subheader("📈 Momentum Trend")
st.markdown(
    "Indicates whether media narrative is **Rising (⬆)**, **Declining (⬇)**, or **Stable (➡)** for each leader/party."
)

for _, row in df.iterrows():
    if row["Momentum"] > 0:
        arrow = "⬆ Rising"
    elif row["Momentum"] < 0:
        arrow = "⬇ Declining"
    else:
        arrow = "➡ Stable"
    st.write(f"**{row['Name']}**: {arrow} ({row['Momentum']})")

# -----------------------
# Confidence Gauges
# -----------------------
st.subheader("🎯 Confidence Gauges")
st.markdown(
    "Shows the overall media confidence score (MCI v2) as a gauge. Higher value → stronger media perception."
)

cols = st.columns(len(df))
for i, row in df.iterrows():
    gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=row["Scenario_Score"],
            title={"text": row["Name"]},
            gauge={
                "axis": {"range": [-0.5, 0.5]},
                "bar": {"color": "blue"},
            },
        )
    )
    cols[i].plotly_chart(gauge, use_container_width=True)

# -----------------------
# Detailed Table
# -----------------------
st.subheader("📊 Detailed Comparison")
st.markdown(
    "Shows numeric breakdown of Sentiment, Volume, Momentum, and overall Scenario Score for all leaders/parties."
)
st.dataframe(df.sort_values("Scenario_Score", ascending=False))

# -----------------------
# Daily Mentions Trend
# -----------------------
st.subheader("📅 Daily Mentions Trend (Last 60 Days)")
st.markdown(
    "Shows how often each leader/party was mentioned in the news daily. Each line shows raw daily counts."
)

targets = df["Name"].tolist()

for target in targets:
    variants = patterns_dict[target]
    pattern = r"\b(?:" + "|".join(re.escape(v) for v in variants) + r")\b"
    temp = news_df[
        news_df["title"].str.lower().str.contains(pattern)
        | news_df["content"].str.lower().str.contains(pattern)
    ]
    temp_grouped = temp.groupby("date").size().reset_index(name="mentions")
    fig = px.line(
        temp_grouped, x="date", y="mentions", title=f"Daily mentions of {target}"
    )
    st.plotly_chart(fig, use_container_width=True)

# -----------------------
# Party-to-Leader Correlation
# -----------------------
if view_option == "Parties":
    st.subheader("🔗 Party-to-Leader Influence")
    st.markdown(
        "Shows how leader mentions correlate with their party's media coverage. Higher ratio → leader drives more party attention."
    )

    party_leader_map = {
        "CPN_UML": ["KP_Oli"],
        "RSP": ["Balen_Shah"],
        "Nepali_Congress": ["Gagan_Thapa"],
    }

    corr_data = []
    for party, leaders in party_leader_map.items():
        for leader in leaders:
            party_variants = party_patterns[party]
            leader_variants = leader_patterns[leader]
            party_pattern = (
                r"\b(?:" + "|".join(re.escape(v) for v in party_variants) + r")\b"
            )
            leader_pattern = (
                r"\b(?:" + "|".join(re.escape(v) for v in leader_variants) + r")\b"
            )

            party_mentions = news_df[
                news_df["title"].str.lower().str.contains(party_pattern)
                | news_df["content"].str.lower().str.contains(party_pattern)
            ].shape[0]
            leader_mentions = news_df[
                news_df["title"].str.lower().str.contains(leader_pattern)
                | news_df["content"].str.lower().str.contains(leader_pattern)
            ].shape[0]
            correlation = leader_mentions / (party_mentions + 1)
            corr_data.append(
                {
                    "Party": party,
                    "Leader": leader,
                    "Leader_to_Party_Ratio": round(correlation, 3),
                }
            )
    corr_df = pd.DataFrame(corr_data)
    st.dataframe(corr_df)
