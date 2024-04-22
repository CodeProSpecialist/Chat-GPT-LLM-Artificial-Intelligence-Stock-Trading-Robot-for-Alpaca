
import alpaca_trade_api as tradeapi
import os
import numpy as np
import yfinance as yf
import talib
from llama import Llama
import pytz
from datetime import datetime
import time

# ******** No, this is not fully working just yet. More code being worked on. ********


# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

# Set up Llama API credentials
llama_api = Llama(os.environ['LLAMA_API_KEY'], os.environ['LLAMA_API_SECRET'])

# Define the stock symbol and time frame
stock_symbol = 'AAPL'
time_frame = '1y'

# Fetch historical data for the past year
hist_data = yf.download(stock_symbol, period=time_frame, interval='1d')

# Calculate technical indicators
hist_data['MA_50'] = talib.SMA(hist_data['Close'], 50)
hist_data['MA_200'] = talib.SMA(hist_data['Close'], 200)
hist_data['RSI'] = talib.RSI(hist_data['Close'], 14)

# Define the market sentiment indicators
def calculate_sentiment(data):
    if data['MA_50'] > data['MA_200']:
        return 1  # Bullish
    elif data['MA_50'] < data['MA_200']:
        return -1  # Bearish
    else:
        return 0  # Neutral

hist_data['Sentiment'] = hist_data.apply(calculate_sentiment, axis=1)

# Define the AI-powered sentiment analysis using Llama
def llama_sentiment(data):
    news_data = llama_api.get_news(stock_symbol, '1d')
    sentiment_score = llama_api.sentiment_analysis(news_data)
    return sentiment_score

hist_data['Llama Sentiment'] = hist_data.apply(llama_sentiment, axis=1)


# Define the maximum profit strategy
def calculate_max_profit(data):
    if data['Sentiment'] == 1 and data['Llama Sentiment'] > 0.5:  # Bullish and positive sentiment
        buy_price = data['Close'] * 0.98
        sell_price = data['Close'] * 1.02
    elif data['Sentiment'] == -1 and data['Llama Sentiment'] < 0.5:  # Bearish and negative sentiment
        buy_price = data['Close'] * 0.95
        sell_price = data['Close'] * 1.05
    else:  # Neutral or conflicting sentiment
        buy_price = data['Close'] * 0.99
        sell_price = data['Close'] * 1.01
    return buy_price, sell_price

hist_data['Buy Price'], hist_data['Sell Price'] = zip(*hist_data.apply(calculate_max_profit, axis=1))

# Backtest the strategy
def backtest_strategy(data):
    profits = []
    for i in range(len(data) - 1):
        if data['Buy Price'].iloc[i] < data['Close'].iloc[i] and data['Sell Price'].iloc[i] > data['Close'].iloc[i+1]:
            profit = (data['Sell Price'].iloc[i] - data['Buy Price'].iloc[i]) / data['Buy Price'].iloc[i]
            profits.append(profit)
    return np.mean(profits)

backtest_profit = backtest_strategy(hist_data)
print(f'Backtest profit: {backtest_profit:.2f}%')

# Define the AI-powered research function
def research_market_conditions():
    # Use Llama AI agents to research market conditions
    news_data = llama_api.get_news(stock_symbol, '1d')
    sentiment_score = llama_api.sentiment_analysis(news_data)
    technical_indicators = llama_api.technical_analysis(hist_data)

    # Determine market conditions
    if sentiment_score < 0.5 and technical_indicators['MA_50'] < technical_indicators['MA_200']:
        market_condition = 'Bearish'
    elif sentiment_score > 0.5 and technical_indicators['MA_50'] > technical_indicators['MA_200']:
        market_condition = 'Bullish'
    else:
        market_condition = 'Neutral'

    return market_condition


# Maintenance loop
while True:
    eastern_time = pytz.timezone('US/Eastern')
    current_time = datetime.now(eastern_time)
    print(f'Current time: {current_time.strftime("%Y-%m-%d %H:%M:%S")}')

    # Research market conditions every 30 minutes
    if current_time.minute % 30 == 0:
        market_condition = research_market_conditions()
        print(f'Market condition: {market_condition}')

        # Adjust buying/selling strategies accordingly
        if market_condition == 'Bearish':
            buy_price = hist_data['Close'].rolling(window=14).mean().iloc[-1]
        elif market_condition == 'Bullish':
            buy_price = hist_data['Open'].iloc[-1] * 0.9915
        else:
            buy_price = hist_data['Close'].iloc[-1] * 0.99

        sell_price = buy_price * 1.02

    # Run the trading bot
    trading_bot(stock_symbol, buy_price, sell_price)

    # Sleep for 1 minute
    time.sleep(60)
