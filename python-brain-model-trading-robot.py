import os
import pytz
from datetime import datetime, timedelta, date
from datetime import time as time2
import yfinance as yf
from ollama import chat
import alpaca_trade_api as tradeapi
import logging
import time
import subprocess

# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api2 = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

# run the OLLAMA server process if it did not start automatically
# in a seperate command terminal run:
# ollama serve

subprocess.run(["sudo", "systemctl", "stop", "ollama"])

subprocess.run(["gnome-terminal", "--", "ollama", "serve"])

# Configure logging
logging.basicConfig(filename='important-program-messages.txt', level=logging.INFO)


def get_stocks_to_trade():
    try:
        with open('list-of-stocks-to-buy.txt', 'r') as file:
            symbols = [line.strip() for line in file.readlines()]

        if not symbols:
            print("\n")
            print(
                "********************************************************************************************************")
            print(
                "*   Error: The file list-of-stocks-to-buy.txt doesn't contain any stock symbols.                       *")
            print(
                "*   This Robot does not work until you place stock symbols in the file named:                          *")
            print(
                "*                     list-of-stocks-to-buy.txt                                                        *")
            print(
                "********************************************************************************************************")
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


def submit_buy_order(symbol, quantity):
    account_info = api2.get_account()
    cash_available = float(account_info.cash)
    current_price = get_current_price(symbol)

    if cash_available >= current_price:
        # Convert symbol from BRK-B to BRK.B if necessary
        symbol = symbol.replace('-', '.')

        api2.submit_order(
            symbol=symbol,
            qty=quantity,
            side='buy',
            type='market',
            time_in_force='day'
        )
        logging.info(f"Bought {quantity} shares of {symbol} at ${current_price:.2f}")


def submit_sell_order(symbol, quantity):
    account_info = api2.get_account()
    day_trade_count = account_info.daytrade_count

    current_price = get_current_price(symbol)

    try:
        position = api2.get_position(symbol)
    except Exception as e:
        logging.error(f"Error getting position: {e}")
        return

    if position.qty != '0':
        bought_price = float(position.avg_entry_price)

        if day_trade_count < 3 and current_price >= bought_price * 1.005:
            api2.submit_order(
                symbol=symbol,
                qty=quantity,
                side='sell',
                type='market',
                time_in_force='day'
            )
            logging.info(f"Sold {quantity} shares of {symbol} at ${current_price:.2f}")
    else:
        logging.info(f"You don't own any shares of {symbol}, so no sell order was submitted.")


def execute_trade(symbol, signal, quantity):
    if signal.startswith("buy"):
        submit_buy_order(symbol, quantity)
    elif signal.startswith("sell"):
        submit_sell_order(symbol, quantity)
    else:
        logging.info(f"Holding {symbol}")

def stop_if_stock_market_is_closed():
    # Check if the current time is within the stock market hours
    # Set the stock market open and close times
    market_open_time = time2(9, 27)
    market_close_time = time2(16, 0)

    while True:
        # Get the current time in Eastern Time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        current_time = now.time()

        # Check if the current time is within market hours
        if now.weekday() <= 4 and market_open_time <= current_time <= market_close_time:
            break

        print("\n")
        print('''

            2024 Edition of the Artificial Intelligence Stock Trading Robot 
           _____   __                   __             ____            __            __ 
          / ___/  / /_  ____   _____   / /__          / __ \  ____    / /_   ____   / /_
          \__ \  / __/ / __ \ / ___/  / //_/         / /_/ / / __ \  / __ \ / __ \ / __/
         ___/ / / /_  / /_/ // /__   / ,<           / _, _/ / /_/ / / /_/ // /_/ // /_  
        /____/  \__/  \____/ \___/  /_/|_|         /_/ |_|  \____/ /_.___/ \____/ \__/  

                                                  https://github.com/CodeProSpecialist

                       Featuring Artificial Intelligence LLM Decision Making   

         ''')
        print(f'Current date & time (Eastern Time): {now.strftime("%A, %B %d, %Y, %I:%M:%S %p")}')
        print("Stockbot only works Monday through Friday: 9:30 am - 4:00 pm Eastern Time.")
        print("Stockbot begins watching stock prices early at 9:27 am Eastern Time.")
        print("Waiting until Stock Market Hours to begin the Stockbot Trading Program.")
        print("\n")
        print("\n")
        time.sleep(60)  # Sleep for 1 minute and check again. Keep this under the p in print.

def main():
    symbols = get_stocks_to_trade()
    if not symbols:
        return

    while True:
        try:
            stop_if_stock_market_is_closed()  # comment this line to debug the Python code
            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")

            cash_balance = round(float(api2.get_account().cash), 2)

            print("------------------------------------------------------------------------------------")
            print(" 2024 Edition of the Artificial Intelligence Stock Trading Robot ")
            print("by https://github.com/CodeProSpecialist")
            print("------------------------------------------------------------------------------------")
            print(f"  {current_time_str} Cash Balance: ${cash_balance}")
            day_trade_count = api2.get_account().daytrade_count
            print("\n")
            print(f"Current day trade number: {day_trade_count} out of 3 in 5 business days")
            print("\n")

            for symbol in symbols:
                try:
                    previous_price = get_14_days_price(symbol)
                    current_price = get_current_price(symbol)
                    debug_print_14_days_prices = get_14_days_price(symbol)
                    X = calculate_percentage_change(current_price, previous_price)
                    Y = 14
                    signal = trading_robot(symbol, X, Y)
                    cash_balance = float(api2.get_account().cash)
                    quantity = int(cash_balance / current_price)
                    if quantity < 1:
                        quantity = 0
                    if quantity >= 1:
                        quantity = 1
                    execute_trade(symbol, signal, quantity)
                    print(f"Symbol: {symbol}")
                    print(f"Current Price: {current_price}")
                    # debug print 14 days prices
                    #print(f"Debug printing 14 days Prices: {debug_print_14_days_prices}")
                    print(f"Decision: {signal}")
                    print("\n")
                    logging.info(f"Signal: {signal}")
                    time.sleep(1)  # Add a 1-second delay

                except Exception as e:     # this is under the t in try
                    logging.error(f"Error: {e}")
                    time.sleep(5)
                    
            print("\n")
            print("Waiting 30 seconds ")
            print("\n")
            time.sleep(30)  # keep this under the "f" in for symbol
        except Exception as e:     # this is under the t in try
            logging.error(f"Error in main loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(5)
