import yfinance as yf
import numpy as np
from llama3 import LLaMA
import alpaca_trade_api as tradeapi

# Set API credentials
alpaca_api_key = 'YOUR_API_KEY'
alpaca_secret_key = 'YOUR_SECRET_KEY'

# Create Alpaca API connection
alpaca_api = tradeapi.REST(alpaca_api_key, alpaca_secret_key)

# Load LLaMA model
llama_model = LLaMA()

# Set trading parameters
trading_period = 14  # days
min_profit_margin = 0.05  # minimum profit margin (5%)
max_drawdown = 0.1  # maximum drawdown (10%)

# Get ETF funds list from Alpaca
etf_funds_list = alpaca_api.list_etfs()

# Initialize data structures for trading decisions
buy_decisions = []
sell_decisions = []

for etf in etf_funds_list:
    # Get historical prices for the ETF fund
    etf_data = yf.download(etf.symbol, period=f'{trading_period}d', interval='1d')
    prices = etf_data['Close'].values

    # Calculate returns and drawdowns
    returns = np.diff(np.log(prices)) / np.diff(prices).mean()
    drawdowns = (prices - np.max(prices)) / (np.max(prices) - np.min(prices))

    # Use LLaMA to predict ETF fund performance
    llama_input = {'returns': returns, 'drawdowns': drawdowns}
    prediction = llama_model.predict(llama_input)

    # Make trading decisions based on predictions
    if prediction > 0:
        buy_decisions.append((etf.symbol, prediction))
    elif prediction < 0:
        sell_decisions.append((etf.symbol, -prediction))

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
