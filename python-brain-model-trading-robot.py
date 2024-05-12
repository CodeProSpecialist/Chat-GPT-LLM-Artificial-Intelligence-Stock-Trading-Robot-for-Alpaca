import os
import pytz
from datetime import datetime, timedelta, date
from datetime import time as time2
import yfinance as yf
from ollama import chat
import alpaca_trade_api as tradeapi
import logging
import schedule
import time
import subprocess
import talib
import numpy as np

# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api2 = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

# run the OLLAMA server process if it did not start automatically
# in a seperate command terminal run:
# ollama serve

purchased_today = {}

global close_prices, time_period

# Function to check if OLLAMA server service is running
def is_ollama_running():
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "ollama"], check=True)
        return True  # OLLAMA server service is running
    except subprocess.CalledProcessError:
        return False  # OLLAMA server service is not running

# Check if OLLAMA server service is running
if is_ollama_running():
    # If OLLAMA server service is running, stop it
    subprocess.run(["sudo", "systemctl", "stop", "ollama"])

subprocess.run(["sudo", "pkill", "ollama"])

time.sleep(2)

subprocess.run(["gnome-terminal", "--", "ollama", "serve"])

time.sleep(1)

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

def calculate_rsi(close_prices, time_period=14):
    rsi = talib.RSI(np.array(close_prices), timeperiod=time_period)
    return rsi[-1]

def calculate_moving_averages(close_prices, short_window=50, long_window=100):
    short_ma = talib.SMA(np.array(close_prices), timeperiod=short_window)
    long_ma = talib.SMA(np.array(close_prices), timeperiod=long_window)
    return short_ma[-1], long_ma[-1]

def get_average_true_range(symbol):
    symbol = symbol.replace('.', '-')  # Replace '.' with '-'
    ticker = yf.Ticker(symbol)
    data = ticker.history(period='30d')
    atr = talib.ATR(data['High'].values, data['Low'].values, data['Close'].values, timeperiod=22)
    return atr[-1]

def get_atr_low_price(symbol):
    atr_value = get_average_true_range(symbol)
    current_price = get_current_price(symbol)
    return round(current_price - 0.10 * atr_value, 4)

def get_atr_high_price(symbol):
    atr_value = get_average_true_range(symbol)
    current_price = get_current_price(symbol)
    return round(current_price + 0.40 * atr_value, 4)

def trading_robot(symbol, X, Y):
    symbol = symbol.replace('.', '-')  # Replace '.' with '-'
    stock_data = yf.Ticker(symbol)
    history_data = stock_data.history(period='180d')
    close_prices = history_data['Close']
    high_prices = history_data['High']
    low_prices = history_data['Low']
    volume = history_data['Volume']
    rsi = calculate_rsi(close_prices)
    short_ma, long_ma = calculate_moving_averages(close_prices)
    fourteen_days_ago_price = get_14_days_price(symbol)
    current_price = get_current_price(symbol)
    fourteen_days_change = calculate_percentage_change(current_price, fourteen_days_ago_price)
    # Calculate additional technical indicators
    avg_volume = np.mean(volume)
    today_new_volume = history_data['Volume'].iloc[-1]

    # Calculate Bollinger Bands
    bbands = talib.BBANDS(np.array(close_prices), timeperiod=14, nbdevup=2, nbdevdn=2)
    upper_band, middle_band, lower_band = bbands
    upper_band_value = upper_band[-1]
    middle_band_value = middle_band[-1]
    lower_band_value = lower_band[-1]

    atr_low_price = get_atr_low_price(symbol)
    atr_high_price = get_atr_high_price(symbol)

    # debug print the ATR, Volume, and the bbands below
    print("\n")
    print(f"Making a decision for: {symbol}")
    print(f"Bollinger Bands: {upper_band_value:.2f}, {middle_band_value:.2f}, {lower_band_value:.2f}")
    print(f"ATR low price: {atr_low_price:.2f}")
    print(f"ATR high price: {atr_high_price:.2f}")
    # Also, atr is an array, so you need to access its last element
    print(f"Current Volume: {today_new_volume:2f}")
    print(f"Average Volume: {avg_volume:.2f}")
    print("\n")
    # Get yesterday's closing price, today's opening price, and today's current price
    yesterday_close = close_prices.iloc[-2]
    today_open = history_data.iloc[-1]['Open']
    today_current = current_price
    # Check for bear or bull market
    if fourteen_days_change > 0:
        market_trend = 'bull'
    else:
        market_trend = 'bear'
    # Create a message to send to the chatbot
    content = (
        f"Yes, you can help me with this important decision."
        f"Yes, you are a helpful market trading assistant."
        f"{symbol} price changed by {X}% in the past {Y} days. "
        f"The RSI is {rsi:.2f} and the 50-day MA is {short_ma:.2f} "
        f"and the 200-day MA is {long_ma:.2f}. "
        f"The price has changed by {fourteen_days_change:.2f}% in the past 14 days. "
        f"Yesterday's closing price was {yesterday_close:.2f}, today's opening price was {today_open:.2f}, "
        f"and today's current price is {today_current:.2f}. "
        f"The Average True Range (ATR) low price is {atr_low_price:.2f}. "
        f"It is a better idea to buy near the Average True Range low price. "
        f"The Average True Range (ATR) high price is {atr_high_price:.2f}. "
        f"It is a better idea to sell near the Average True Range high price. "
        f"The Current Volume is {today_new_volume:2f}. "
        f"The Average Volume is {avg_volume:.2f}. "
        f"It is a better idea to buy when Volume is lower or equal to the Average Volume."
        f"It is a better idea to sell when Volume and RSI are both increased, "
        f"and when Volume is equal to or greater than average volume. "
        f"Today's Bollinger Band prices are: upper band price:{upper_band_value:.2f}, middle band price:{middle_band_value:.2f}, lower band price:{lower_band_value:.2f}"
        f"We buy equal to or below the Bollinger Band lower band price, and we sell equal to or above the upper band price. "
        f"The market trend is {market_trend}. "
        f"We buy during a bull market trend and we stop buying to hold during a bear market trend. "
        f"Should I buy or sell {symbol}? "
        f"Instructions: Buy if RSI < 30 and 50-day MA > 200-day MA and the price has increased in the past 14 days "
        f"Sell if RSI > 70 and 50-day MA < 200-day MA and the price has decreased in the past 14 days "
        f"We buy equal to or below the Bollinger Band lower band price, and we sell equal to or above the upper band price: or else we hold. "
        f"Hold otherwise. Answer only with buy {symbol}, sell {symbol}, or hold {symbol}."
    )
    messages = [{'role': 'user', 'content': content}]
    response = chat('llama3:8b-instruct-q4_0', messages=messages)
    response = response['message']['content'].strip().lower()
    if "buy" in response:
        return f"buy {symbol}"
    elif "sell" in response:
        return f"sell {symbol}"
    else:
        return f"hold {symbol}"


def submit_buy_order(symbol, quantity):
    # Get the current time in Eastern Time
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    current_time = now.time()

    # Define the time range for trading (10:15 to 16:00)
    trading_start = time2(10, 15)
    trading_end = time2(16, 0)

    # Check if the current time is within the trading hours
    if current_time >= trading_start and current_time <= trading_end:
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
            # Add the symbol to the purchased_today dictionary
            purchased_today[symbol] = True
    else:
        logging.info("Trading outside profit trading strategy hours, buy order not submitted.")

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
        # sell quickly when the market quickly changes for at least 1 penny more than the purchased price. 
        if day_trade_count < 3 and current_price >= bought_price + 0.01:
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

def sell_yesterdays_purchases():
    """
    Sell all owned positions that were purchased before today if the purchased price is less than the current price + 0.10 cents.
    """
    account = api2.get_account()
    positions = api2.list_positions()

    today = datetime.now(pytz.timezone('US/Eastern')).date()
    for position in positions:
        symbol = position.symbol
        current_price = get_current_price(symbol)
        bought_price = float(position.avg_entry_price)

        # Check if the symbol is not in the purchased_today dictionary
        if symbol not in purchased_today:
            # Check if the last trade date is not today
            if current_price >= bought_price + 0.01:
                quantity = int(position.qty)
                submit_sell_order(symbol, quantity)
                logging.info(f"Sold {quantity} shares of {symbol} at ${current_price:.2f}")

def clear_purchased_today():
    global purchased_today
    purchased_today = {}

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
            #stop_if_stock_market_is_closed()  # comment this line to debug the Python code
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

            # Clear the purchased_today dictionary at the start of each day
            schedule.every().day.at("09:27").do(clear_purchased_today)  # Run at 09:30am every day

            sell_yesterdays_purchases()

            #if day_trade_count < 3:
                #sell_yesterdays_purchases()  # Only run this function if day trade count is less than 3

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
