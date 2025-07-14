# ==============================================================================
# DATA SCIENCE PORTFOLIO PROJECT (FINTECH)
# Correlating Financial News Sentiment with Stock Volatility
#
# Author: Sourabh Sonker 
#
# This script performs an end-to-end analysis by:
# 1. Fetching recent news headlines for specific stocks from NewsAPI.
# 2. Downloading corresponding stock price data from Yahoo Finance.
# 3. Performing sentiment analysis on the news headlines using VADER.
# 4. Calculating daily stock price volatility.
# 5. Merging the two datasets, mapping news dates to their trading days.
# 6. Analyzing the correlation and visualizing the result.
# ==============================================================================

import os
import pandas as pd
import requests
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from datetime import date, timedelta
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt


# ==============================================================================
# STEP 1: SETUP AND CONFIGURATION
# ==============================================================================
print("--- Step 1: Initializing Configuration ---")

# --- User-Defined Variables ---
# IMPORTANT: Replace with your actual NewsAPI key
NEWS_API_KEY = "1aa05b2453c4407fb25bf6dae107a56a"
STOCK_MAPPING = {"Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT"}
DATA_DIR = "project_data"

# --- Date Configuration ---
# To ensure the 'next trading day' logic works, we shift the analysis window back.
BASE_DATE = date.today() - timedelta(days=4)
END_DATE = BASE_DATE
START_DATE = END_DATE - timedelta(days=4)

# --- Derived Variables & Environment Setup ---
os.makedirs(DATA_DIR, exist_ok=True)
COMPANY_NAMES = list(STOCK_MAPPING.keys())
STOCK_TICKERS = list(STOCK_MAPPING.values())

print(f"Configuration loaded. Analyzing from {START_DATE} to {END_DATE}.")


# ==============================================================================
# STEP 2: FETCH NEWS DATA
# ==============================================================================
print("\n--- Step 2: Fetching News Data from NewsAPI ---")

all_articles = []
for company, ticker in STOCK_MAPPING.items():
    print(f"Fetching articles for {company}...")
    query = f'("{company}" OR "{ticker}") AND (stock OR market)'
    url = (f'https://newsapi.org/v2/everything?'
           f'q={query}&from={START_DATE}&to={END_DATE}&language=en&'
           f'sortBy=publishedAt&pageSize=100&apiKey={NEWS_API_KEY}')
           
    response = requests.get(url)
    if response.status_code == 200:
        articles_json = response.json().get('articles', [])
        for article in articles_json:
            article['company'] = company
        all_articles.extend(articles_json)
        print(f"Fetched {len(articles_json)} articles for {company}.")
    else:
        print(f"Failed to fetch news for {company}: {response.text}")

raw_news_df = pd.DataFrame(all_articles)

if raw_news_df.empty:
    print("\nCRITICAL FAILURE: No news articles were fetched. Halting script.")
    exit()
else:
    print(f"\nTotal articles fetched: {len(raw_news_df)}.")


# ==============================================================================
# STEP 3: PROCESS SENTIMENT DATA
# ==============================================================================
print("\n--- Step 3: Processing and Analyzing Sentiment ---")

analyzer = SentimentIntensityAnalyzer()
raw_news_df['sentiment_score'] = raw_news_df['title'].apply(lambda title: analyzer.polarity_scores(str(title))['compound'])
raw_news_df['date'] = pd.to_datetime(raw_news_df['publishedAt']).dt.date
daily_sentiment_df = raw_news_df.groupby(['company', 'date'])['sentiment_score'].mean().reset_index()
daily_sentiment_df.columns = daily_sentiment_df.columns.str.lower()

print(f"Sentiment analysis complete. Found {len(daily_sentiment_df)} unique company/date rows.")


# ==============================================================================
# STEP 4: FETCH STOCK PRICE DATA
# ==============================================================================
print("\n--- Step 4: Fetching Stock Price Data from yfinance ---")

FETCH_START_DATE = START_DATE - timedelta(days=30)
FETCH_END_DATE = END_DATE + timedelta(days=1)
stock_data_raw = yf.download(STOCK_TICKERS, start=FETCH_START_DATE, end=FETCH_END_DATE)

stock_df = stock_data_raw.stack().reset_index()
stock_df.columns = stock_df.columns.str.lower()
stock_df.rename(columns={'level_1': 'ticker'}, inplace=True)
REVERSE_STOCK_MAPPING = {v: k for k, v in STOCK_MAPPING.items()}
stock_df['company'] = stock_df['ticker'].map(REVERSE_STOCK_MAPPING)
final_stock_columns = ['company', 'ticker', 'date', 'open', 'high', 'low', 'close', 'adj close', 'volume']
existing_cols = [col for col in final_stock_columns if col in stock_df.columns]
stock_df = stock_df[existing_cols]

print("Stock price data processed.")


# ==============================================================================
# STEP 5: MERGE DATASETS
# ==============================================================================
print("\n--- Step 5: Calculating Volatility and Merging Data ---")

# Ensure date columns are in datetime format
stock_df['date'] = pd.to_datetime(stock_df['date'])
daily_sentiment_df['date'] = pd.to_datetime(daily_sentiment_df['date'])

# Calculate volatility
stock_df['volatility'] = (stock_df['high'] - stock_df['low']) / stock_df['low']
all_trading_days = sorted(stock_df['date'].unique())

def get_trading_date(news_date):
    """Finds the first trading day that is ON or AFTER the news date."""
    for trading_day in all_trading_days:
        if trading_day >= news_date:
            return trading_day
    return pd.NaT

daily_sentiment_df['trading_date'] = daily_sentiment_df['date'].apply(get_trading_date)

# Prepare for merge
stock_df_for_merge = stock_df.rename(columns={'date': 'trading_date', 'volatility': 'volatility_on_trading_date'})

final_df = pd.merge(
    daily_sentiment_df,
    stock_df_for_merge[['company', 'trading_date', 'volatility_on_trading_date']],
    on=['company', 'trading_date'],
    how='inner'
)

if final_df.empty:
    print("\nMERGE FAILED: The final DataFrame is empty. Check API limits or date ranges.")
else:
    file_path = os.path.join(DATA_DIR, "final_analysis_data.csv")
    final_df.to_csv(file_path, index=False)
    print(f"\nSUCCESS! Merged data saved to: {file_path}")
    print("Preview of the final merged data:")
    print(final_df.head())


# ==============================================================================
# STEP 6: FINAL ANALYSIS AND VISUALIZATION
# ==============================================================================
print("\n--- Step 6: Final Analysis and Visualization ---")

if 'final_df' in locals() and not final_df.empty:
    
    # --- Correlation Analysis ---
    if len(final_df) < 3:
        print("Insufficient data for meaningful correlation analysis (less than 3 data points).")
    else:
        correlation = final_df['sentiment_score'].corr(final_df['volatility_on_trading_date'])
        print(f"\nOverall Pearson Correlation between Sentiment and Volatility: {correlation:.4f}")

    # --- Visualization ---
    print("\nGenerating visualizations...")
    sns.set_theme(style="whitegrid")
    
    # Using relplot is more robust for scatter plots with hue than lmplot's figure-level nature
    p = sns.relplot(
        data=final_df,
        x='sentiment_score',
        y='volatility_on_trading_date',
        hue='company',
        s=150, # Increase marker size
        height=6,
        aspect=1.5
    )
    p.ax.set_title('News Sentiment vs. Same-Day Stock Volatility', fontsize=16, pad=20)
    p.set_axis_labels('Average Daily Sentiment Score', 'Same-Day Price Volatility', fontsize=12)
    
    # Add a regression line separately
    sns.regplot(
        data=final_df,
        x='sentiment_score',
        y='volatility_on_trading_date',
        scatter=False, # Don't draw the scatter points again
        ci=None,
        ax=p.ax,
        color='black',
        line_kws={'linestyle':'--'}
    )
    
    plot_path = os.path.join(DATA_DIR, "sentiment_vs_volatility.png")
    plt.savefig(plot_path)
    print(f"Analysis plot saved to: {plot_path}")

    plt.show()

else:
    print("Analysis skipped because the final DataFrame was empty.")

print("\n--- Project Complete ---")