import os
import pytz
from datetime import datetime
import yfinance as yf
from ollama import chat
import alpaca_trade_api as tradeapi
import logging
import time

# Configure logging
logging.basicConfig(filename='important-program-messages.txt', level=logging.INFO)

def get_stocks_to_trade():
    try:
        with open('list-of-stocks-to-buy.txt', 'r') as file:
            symbols = [line.strip() for line in file.readlines()]

        if not symbols:
            print("\n")
            print("********************************************************************************************************")
            print("*   Error: The file list-of-stocks-to-buy.txt doesn't contain any stock symbols.                       *")
            print("*   This Robot does not work until you place stock symbols in the file named:                          *")
            print("*                     list-of-stocks-to-buy.txt                                                        *")
            print("********************************************************************************************************")
            print("\n")

        return symbols
    except Exception as e:
        logging.error(f"Error reading stock symbols: {e}")
        return []

def get_14_days_price(symbol):
    symbol = symbol.replace('.', '-')  # Replace '.' with '-'
    stock_data = yf.Ticker(symbol)
    return round(stock_data.history(period='14d')['Close'].iloc[0], 4)

def get_current_price(symbol):
    symbol = symbol.replace('.', '-')  # Replace '.' with '-'
    stock_data = yf.Ticker(symbol)
    return round(stock_data.history(period='1d')['Close'].iloc[0], 4)

def calculate_percentage_change(current_price, previous_price):
    return ((current_price - previous_price) / previous_price) * 100

def trading_robot(symbol, X, Y):
    messages = [
        {
            'role': 'user',
            'content': f"{symbol} price changed by {X}% in the past {Y} days. Should I buy or sell {symbol}? Instructions: Buy at low price and if X <=0, Sell at high price and only if X >= 0, Hold if X did not change more than 1% or -1%. Where X is the percentage change and Y is the number of days. Answer only with buy {symbol}, sell {symbol}, or hold {symbol}.",
        },
    ]
    response = chat('llama3:8b', messages=messages)
    response = response['message']['content'].strip().lower()
    if "buy" in response:
        return f"buy {symbol}"
    elif "sell" in response:
        return f"sell {symbol}"
    else:
        return f"hold {symbol}"

def submit_buy_order(symbol, quantity, target_buy_price):
    account_info = api.get_account()
    cash_available = float(account_info.cash)
    current_price = get_current_price(symbol)

    if current_price <= target_buy_price and cash_available >= current_price:
        # Convert symbol from BRK-B to BRK.B if necessary
        symbol = symbol.replace('-', '.')

        api.submit_order(
            symbol=symbol,
            qty=quantity,
            side='buy',
            type='market',
            time_in_force='gtc'
        )
        logging.info(f"Bought {quantity} shares of {symbol} at ${current_price:.2f}")

def submit_sell_order(symbol, quantity, target_sell_price):
    account_info = api.get_account()
    day_trade_count = account_info.daytrade_count

    current_price = get_current_price(symbol)
    
    try:
        position = api.get_position(symbol)
    except Exception as e:
        logging.error(f"Error getting position: {e}")
        return

    if position.qty != '0':
        bought_price = float(position.avg_entry_price)

        if current_price >= target_sell_price and day_trade_count < 3 and current_price >= bought_price * 1.005:
            api.submit_order(
                symbol=symbol,
                qty=quantity,
                side='sell',
                type='market',
                time_in_force='gtc'
            )
            logging.info(f"Sold {quantity} shares of {symbol} at ${current_price:.2f}")
    else:
        logging.info(f"You don't own any shares of {symbol}, so no sell order was submitted.")

def execute_trade(symbol, signal, quantity, target_buy_price, target_sell_price):
    if signal.startswith("buy"):
        submit_buy_order(symbol, quantity, target_buy_price)
    elif signal.startswith("sell"):
        submit_sell_order(symbol, quantity, target_sell_price)
    else:
        logging.info(f"Holding {symbol}")

def main():
    symbols = get_stocks_to_trade()
    if not symbols:
        return
    
    # Configure Alpaca API
    API_KEY_ID = os.getenv('APCA_API_KEY_ID')
    API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
    API_BASE_URL = os.getenv('APCA_API_BASE_URL')

    # Initialize Alpaca API
    api = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

    while True:
        try:
            eastern = pytz.timezone('US/Eastern')
            print("\n\n======================================")
            print(f"Today's Date and Time (Eastern Time): {datetime.now(eastern)}")
            print("======================================\n")

            for symbol in symbols:
                try:
                    previous_price = get_14_days_price(symbol)
                    current_price = get_current_price(symbol)
                    X = calculate_percentage_change(current_price, previous_price)
                    Y = 14
                    signal = trading_robot(symbol, X, Y)
                    execute_trade(symbol, signal, 10, 400, 420)
                    print(f"Symbol: {symbol}")
                    print(f"Current Price: {current_price}")
                    print(f"Decision: {signal}")
                    logging.info(f"Signal: {signal}")
                    time.sleep(1)  # Add a 1-second delay
                except Exception as e:
                    logging.error(f"Error: {e}")
                    time.sleep(5)
                    break  # Restart the main loop after 5 seconds
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(5)
