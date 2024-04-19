import yfinance as yf
import numpy as np
from llama3 import LLaMA
import alpaca_trade_api as tradeapi
import os

# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

# Load LLaMA model
llama_model = LLaMA()

# Set trading parameters
trading_period = 14  # days
min_profit_margin = 0.05  # minimum profit margin (5%)
max_drawdown = 0.1  # maximum drawdown (10%)

# Get ETF funds list from Alpaca
etf_funds_list = ['AGQ', 'UGL']

# Initialize data structures for trading decisions
buy_decisions = []
sell_decisions = []

for symbol in etf_funds_list:
    # Get historical prices for the ETF fund
    etf_data = yf.download(tickers=symbol, period=f'{trading_period}d', interval='1d')
    prices = etf_data['Close'].values

    # Calculate returns and drawdowns
    returns = np.diff(np.log(prices)) / np.diff(prices).mean()
    drawdowns = (prices - np.max(prices)) / (np.max(prices) - np.min(prices))

    # Use LLaMA to predict ETF fund performance
    llama_input = {'returns': returns, 'drawdowns': drawdowns}
    prediction = llama_model.predict(llama_input)

    # Make trading decisions based on predictions
    if prediction > 0:
        buy_decisions.append((symbol, prediction))
    elif prediction < 0:
        sell_decisions.append((symbol, -prediction))

# Filter and rank ETF funds by profit margin
buy_ranks = []
sell_ranks = []

for decision in buy_decisions + sell_decisions:
    symbol, profit_margin = decision
    if profit_margin > min_profit_margin:
        buy_ranks.append((symbol, profit_margin))
    elif profit_margin < -min_profit_margin:
        sell_ranks.append((symbol, -profit_margin))

buy_ranks.sort(key=lambda x: x[1], reverse=True)
sell_ranks.sort(key=lambda x: x[1], reverse=True)

# Print the top-ranked ETF funds for buying and selling
print("Top Buying Opportunities:")
for symbol, _ in buy_ranks[:5]:
    print(symbol)

print("\nTop Selling Opportunities:")
for symbol, _ in sell_ranks[:5]:
    print(symbol)
