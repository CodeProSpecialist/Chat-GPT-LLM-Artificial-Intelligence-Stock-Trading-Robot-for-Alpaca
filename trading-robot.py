import os
import pickle
import time
import numpy as np
import yfinance as yf
import talib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import torch
from torch import nn
import alpaca_trade_api as tradeapi
import logging
from datetime import datetime, timedelta, date
from datetime import time as time2
import pytz
import torch
from transformers import LLaMAForSequenceClassification, LLaMATokenizer

# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

# Load LLaMA 3.8B model
model_name = "llama-3.8b"
llama_tokenizer = LLaMATokenizer.from_pretrained(model_name)
llama_model = LLaMAForSequenceClassification.from_pretrained(model_name)

# Load stock symbols from file
with open('list-of-stocks-to-buy.txt', 'r') as f:
    stock_symbols = [line.strip() for line in f.readlines()]

# Define trading parameters
trading_fee = 0.005  # 0.5% trading fee
min_account_balance = 1000  # minimum account balance
max_position_size = 0.1  # maximum position size as a fraction of account balance

# Define technical indicators
def calculate_indicators(data):
    # Calculate simple moving averages
    data['sma_50'] = talib.SMA(data['Close'], timeperiod=50)
    data['sma_200'] = talib.SMA(data['Close'], timeperiod=200)
    
    # Calculate relative strength index
    data['rsi'] = talib.RSI(data['Close'], timeperiod=14)
    
    return data

# Define trading logic
def analyze_market(data):
    # Calculate technical indicators
    data = calculate_indicators(data)
    
    # Get LLaMA's prediction
    input_text = f"Analyze stock market data for the past 14 days: {data}"
    inputs = llama_tokenizer(input_text, return_tensors="pt")
    output = llama_model(**inputs)
    prediction = torch.argmax(output.logits)  # Get the predicted label
    
    # Make trading decision based on LLaMA's prediction
    if prediction == 0:  # bullish
        return 'buy'
    elif prediction == 1:  # bearish
        return 'sell'
    else:
        return 'hold'

# Define trading function
def trade(symbol):
    # Get historical data for the past 14 days
    data = yf.download(symbol, start=date.today() - timedelta(days=14), end=date.today())
    
    # Analyze market and make trading decision
    decision = analyze_market(data)
    
    # Print current market conditions
    print(f"Analyzing {symbol}...")
    print(f"Current market conditions: {data.iloc[-1]['Close']}")
    print(f"LLaMA's prediction: {decision}")
    
    # Execute trade
    if decision == 'buy':
        # Calculate position size
        account_balance = api.get_account().cash
        position_size = min(max_position_size, account_balance * 0.1)
        
        # Place buy order
        api.submit_order(symbol, position_size, 'buy', 'market', 'day')
    elif decision == 'sell':
        # Check day trade count
        account_info = api.get_account()
        day_trade_count = account_info.daytrade_count
        
        if day_trade_count < 3:
            current_price = get_current_price(symbol)
            position = api.get_position(symbol)
            bought_price = float(position.avg_entry_price)
            
            # Check if there is an open sell order for the symbol
            open_orders = api.list_orders(status='open', symbol=symbol)
            if open_orders:
                print(f"There is an open sell order for {symbol}. Skipping sell order.")
                return  # Skip to the next iteration if there's an open sell order
            
            # Sell stocks if the current price is more than 0.5% higher than the purchase price.
            if current_price >= bought_price * 1.005:
                qty = api.get_position(symbol).qty
                api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='day')

# Define function to get current price
def get_current_price(symbol):
    data = yf.download(symbol, start=date.today(), end=date.today())
    return data.iloc[-1]['Close']

# Main trading loop
while True:
    now = datetime.now(pytz.timezone('US/Eastern'))
    current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")
    
    cash_balance = round(float(api.get_account().cash), 2)
    print(f"  {current_time_str} Cash Balance: ${cash_balance}")
    
    day_trade_count = api.get_account().daytrade_count
    print(f"\nCurrent day trade number: {day_trade_count} out of 3 in 5 business days")
    print("\n")
    print("\n")
    print("------------------------------------------------------------------------------------")
    print("\n")
    
    for symbol in stock_symbols:
        trade(symbol)
    
    # Wait for 1 minute before checking again
    time.sleep(60)
