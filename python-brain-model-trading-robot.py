import os, sys
import csv
import pytz
from datetime import datetime, timedelta, date
from datetime import time as time2
import yfinance as yf
from ollama import chat
import alpaca_trade_api as tradeapi
import logging
import schedule
import threading
import calendar
import holidays
import time
import subprocess
import talib
import re
import numpy as np
from tabulate import tabulate

# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api2 = tradeapi.REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

# run the OLLAMA server process if it did not start automatically
# in a separate command terminal run:
# ollama serve

purchased_today = {}

# Create a list of US federal holidays
us_holidays = holidays.US()

global close_prices, time_period, csv_writer, csv_filename, fieldnames

# Define the CSV file and fieldnames
csv_filename = 'log-file-of-buy-and-sell-signals.csv'
fieldnames = ['Date', 'Buy', 'Sell', 'Quantity', 'Symbol', 'Price Per Share']

# Open the CSV file for writing and set up a CSV writer
with open(csv_filename, mode='w', newline='') as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

    # Write the header row
    csv_writer.writeheader()

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

def get_account_balance(date):
    # Get portfolio history for the specified date
    try:
        portfolio_history = api2.get_portfolio_history(
            timeframe='1D',
            date_start=date.strftime("%Y-%m-%d")
        )
        if portfolio_history.equity:
            return portfolio_history.equity[0]
        else:
            raise ValueError("No equity data available for the specified date")
    except Exception as e:
        print(f"Error fetching balance for {date}: {e}")
        return None

def calculate_balance_percentage_change(old_balance, new_balance):
    if old_balance == 0:
        return 0
    return ((new_balance - old_balance) / old_balance) * 100

def get_last_trading_day(date):
    while date.weekday() > calendar.FRIDAY or date in us_holidays:  # Adjust for weekends and holidays
        date -= timedelta(days=1)
    return date

def print_account_balance_change():
    # Get today's date
    today = datetime.now().date()

    # Adjust today to the last trading day if today is Saturday, Sunday, or a holiday
    if today.weekday() == calendar.SATURDAY:
        today -= timedelta(days=1)
    elif today.weekday() == calendar.SUNDAY:
        today -= timedelta(days=2)

    # Ensure today is not a holiday
    if today in us_holidays:
        today = get_last_trading_day(today)

    # Calculate the dates for 7, 14, and 30 days ago
    dates = {
        "Current Balance": today,
        "7 Days Ago": get_last_trading_day(today - timedelta(days=7)),
        "14 Days Ago": get_last_trading_day(today - timedelta(days=14)),
        "30 Days Ago": get_last_trading_day(today - timedelta(days=30))
    }

    # Fetch balances for each date
    balances = {label: get_account_balance(date) for label, date in dates.items()}

    # Get the current balance
    current_balance = balances["Current Balance"]

    # Print balances and percentage changes
    print("---------------------------------------------------")
    for label, balance in balances.items():
        if balance is not None:
            if label == "Current Balance":
                print(f"{label}: ${balance}")
            else:
                percentage_change = calculate_balance_percentage_change(balance, current_balance)
                change_label = {
                    "7 Days Ago": "7 days % Change",
                    "14 Days Ago": "14 days % Change",
                    "30 Days Ago": "1 month % Change"
                }[label]
                change_symbol = '+' if percentage_change >= 0 else '-'
                print(f"{label}: ${balance} | {change_label}: {change_symbol}{abs(percentage_change):.2f}%")
            print("---------------------------------------------------")
        else:
            print(f"{label}: No percentage change data available 7 days ago in your portfolio. "
                  f"Possibly a holiday last week or the Stock Market was closed 7 days ago. "
                  f"Check back tomorrow for percentage change data from your portfolio. ")
            print("---------------------------------------------------")

def get_14_days_price(symbol):
    symbol = symbol.replace('.', '-')  # Replace '.' with '-'
    stock_data = yf.Ticker(symbol)
    return round(stock_data.history(period='14d')['Close'].iloc[0], 4)

def get_current_price(symbol):
    # Replace '.' with '-'
    symbol = symbol.replace('.', '-')
    # Define Eastern Time Zone
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    # Define trading hours
    pre_market_start = time2(4, 0)
    pre_market_end = time2(9, 30)
    market_start = time2(9, 30)
    market_end = time2(16, 0)
    post_market_start = time2(16, 0)
    post_market_end = time2(20, 0)
    # Fetch stock data
    stock_data = yf.Ticker(symbol)
    try:
        if pre_market_start <= now.time() < market_start:
            # Fetch pre-market data
            data = stock_data.history(start=now.strftime('%Y-%m-%d'), interval='1m', prepost=True)
            if not data.empty:
                data.index = data.index.tz_convert(eastern)
                pre_market_data = data.between_time(pre_market_start, pre_market_end)
                current_price = pre_market_data['Close'].iloc[-1] if not pre_market_data.empty else None
                if current_price is None:
                    logging.error("Pre-market: Current Price not found error.")
                    print("Pre-market: Current Price not found error.")
            else:
                current_price = None
                logging.error("Pre-market: Current Price not found error.")
                print("Pre-market: Current Price not found error.")
        elif market_start <= now.time() < market_end:
            # Fetch regular daytime 9:30 - 16:00 market data
            data = stock_data.history(period='1d', interval='1m')
            if not data.empty:
                data.index = data.index.tz_convert(eastern)
                current_price = data['Close'].iloc[-1] if not data.empty else None
                if current_price is None:
                    logging.error("Market hours: Current Price not found error.")
                    print("Market hours: Current Price not found error.")
            else:
                current_price = None
                logging.error("Market hours: Current Price not found error.")
                print("Market hours: Current Price not found error.")
        elif market_end <= now.time() < post_market_end:
            # Fetch post-market data
            data = stock_data.history(start=now.strftime('%Y-%m-%d'), interval='1m', prepost=True)
            if not data.empty:
                data.index = data.index.tz_convert(eastern)
                post_market_data = data.between_time(post_market_start, post_market_end)
                current_price = post_market_data['Close'].iloc[-1] if not post_market_data.empty else None
                if current_price is None:
                    logging.error("Post-market: Current Price not found error.")
                    print("Post-market: Current Price not found error.")
            else:
                current_price = None
                logging.error("Post-market: Current Price not found error.")
                print("Post-market: Current Price not found error.")

        else:
            # Outside of trading hours, get the last close price
            last_close = stock_data.history(period='1d')['Close'].iloc[-1]
            current_price = last_close
    except Exception as e:
        logging.error(f"Error fetching current price for {symbol}: {e}")
        print(f"Error fetching current price for {symbol}: {e}")
        current_price = None

    if current_price is None:
        error_message = f"Failed to retrieve current price for {symbol}."
        logging.error(error_message)
        print(error_message)

    return round(current_price, 4) if current_price else None

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

    now = datetime.now(pytz.timezone('US/Eastern'))
    day_of_week = now.strftime("%A")  # Get the current day of the week
    month = now.strftime("%B")  # Get the current month

    # Determine if today is a day when prices increase or decrease
    if day_of_week in ["Thursday", "Friday"]:
        # Prices increase on Thursday and Friday
        price_trend = "increase"
    elif day_of_week in ["Monday", "Tuesday", "Wednesday"]:
        # Prices decrease on Monday, Tuesday, and Wednesday
        price_trend = "decrease"
    else:
        # For other days, expect prices to not increase much
        price_trend = "stagnant or decrease"

    # Determine if it's a bull or bear market based on the month
    if month in ["May", "June", "July", "November", "December"]:
        market_trend_month = "bull"
    elif month == "February":
        market_trend_month = "bull sometimes"
    else:
        market_trend_month = "bear or stagnant"

    # debug print the ATR, Volume, and the bbands below
    print("\n")
    compact_current_time_str = now.strftime("EST %I:%M:%S %p ")
    print(compact_current_time_str)
    extra_compact_current_time_str = now.strftime("%H:%M:%S")
    print("\n")
    print(f"Making a decision for: {symbol}")
    print("\n")

    yesterday_close = close_prices.iloc[-2]
    today_open = history_data.iloc[-1]['Open']
    today_current = current_price

    if fourteen_days_change > 0:
        market_trend = 'bull'
    else:
        market_trend = 'bear'

    # Retrieve account information
    account_info = api2.get_account()
    account_balance = float(account_info.equity)
    available_cash = float(account_info.cash)
    day_trade_count = api2.get_account().daytrade_count

    # Debug print the account information
    # print(f"Account Balance: ${account_balance:.2f}")
    # print(f"Available Cash: ${available_cash:.2f}")
    # print("Day Trades Remaining:", day_trades_remaining)

    # Update content message to include account information
    content = (
        f"Yes, you can assist me with this decision. "
        f"Your role as a stock market trading assistant is crucial here. "
        f"I need your help with analyzing market data. "
        f"Consider all technical indicators to make an informed decision. "
        f"The current time is: {now.strftime('%H:%M:%S')}. "
        f"We prefer buying during the times: 4:34-5:34 and 10:15-11:15, "
        f"and selling during the times: 9:31-9:38, 15:30-15:59, and 19:30-19:59. "
        f"Buying early during the times range of 4:34-5:34 is mandatory as a default priority, "
        f"especially during bear market trends. "
        f"The crucial and mandatory exception that takes priority over all other default rules "
        f"for buying at the early times is that we never buy during the early hour "
        f"time range of 4:00-10:14 unless the current price is less than yesterday's closing price. "
        f"The default early morning rule for Monday is to never buy during the times: 4:00-10:14. "
        f"We cannot trade after 19:59 or when the market is closed. "
        f"Selling for a profit of 1% or more is advisable at any time. "
        f"The stock symbol {symbol} changed by {X}% in the past {Y} days. "
        f"The RSI is {rsi:.2f}, 50-day MA is {short_ma:.2f}, "
        f"and 100-day MA is {long_ma:.2f}. "
        f"The market trend is {market_trend}. "
        f"We buy during a bull market and hold during a bear market. "
        f"Price changed by {fourteen_days_change:.2f}% in the past 14 days. "
        f"Current Volume is {today_new_volume:2f}. "
        f"Average Volume is {avg_volume:.2f}. "
        f"Better to buy when Volume <= Average Volume. "
        f"Better to sell when RSI > 70 or Volume >= Average Volume. "
        f"Should I buy or sell {symbol}? "
        f"Instructions: Buy if RSI < 30, 50-day MA > 200-day MA, "
        f"and price increased in the past 14 days. "
        f"Sell if RSI > 70, 50-day MA < 200-day MA, "
        f"and price decreased in the past 14 days. "
        f"Today's Bollinger Band prices: upper:{upper_band_value:.2f}, "
        f"middle:{middle_band_value:.2f}, lower:{lower_band_value:.2f}. "
        f"Buy <= lower band price, sell >= upper band price. "
        f"Yesterday's closing price: {yesterday_close:.2f}, "
        f"today's opening price: {today_open:.2f}, and current price: {today_current:.2f}. "
        f"ATR low price: {atr_low_price:.2f}. "
        f"ATR high price: {atr_high_price:.2f}. "
        f"Buy near ATR low, sell near ATR high. "
        f"The current date is {now.strftime('%A, %B %d, %Y')}. "
        f"Today is {day_of_week}. "
        f"Prices usually {price_trend} on {day_of_week}s. "
        f"Prices usually {market_trend_month} in {month}. "
        f"During a bear market the default preferred choice is to sell during the time range of 11:40-12:10. "
        f"On Monday, Tuesday, and Wednesday, the default preferred sell time range is 11:40-12:10. "
        f"On Friday, default mandatory rule is to sell everything 11:40-12:10 because prices decrease until Monday. "
        f"On Friday, default mandatory rule is no buying 11:16-20:00 because prices decrease until Monday. "
        f"Account Balance: {account_balance:.2f}, "
        f"Available Cash: {available_cash:.2f}, "
        f"Current day trade number: {day_trade_count} out of 3 in 5 business days. "
        f"We can only day trade 3 times in 5 business days. "
        f"A day trade is to buy and sell the same stock in the same day. "
        f"Our crucially urgent goal is to reach an account balance "
        f"of $25,001.00 dollars as soon as possible to not be limited "
        f"to the strict requirement of a tiny 3 daytrades in 5 business days. "
        f"Please summarize in 2 to 8 sentences what the decision was based upon. "
        f"The following must be worded exactly like it is shown because it triggers "
        f"a computer command to buy, sell, or hold: "
        f"Respond only with: **buy {symbol}**, **sell {symbol}**, or **hold {symbol}** "

    )

    decision = organized_response(content, symbol)
    return decision


def organized_response(content, symbol):
    messages = [{'role': 'user', 'content': content}]
    response = chat('llama3:8b-instruct-q4_0', messages=messages)
    response_content = response['message']['content'].strip().lower()

    # Debug prints
    # print("\nContent:\n", content, "\n")
    # print("\nMessages:\n", messages, "\n")
    print("\n", response_content, "\n")

    buy_pattern = re.compile(rf"\*\*buy {symbol}\*\*", re.IGNORECASE)
    sell_pattern = re.compile(rf"\*\*sell {symbol}\*\*", re.IGNORECASE)
    hold_pattern = re.compile(rf"\*\*hold {symbol}\*\*", re.IGNORECASE)

    if buy_pattern.search(response_content):
        return f"buy {symbol}"
    elif sell_pattern.search(response_content):
        return f"sell {symbol}"
    elif hold_pattern.search(response_content):
        return f"hold {symbol}"
    else:
        return f"hold {symbol}"


def print_positions(api2, show_price_percentage_change=False):
    positions = api2.list_positions()

    table_data = []
    headers = ["Symbol", "Quantity", "Avg Entry Price"]
    if show_price_percentage_change:
        headers.append("Price Change (%)")

    for position in positions:
        symbol = position.symbol
        quantity = position.qty
        avg_entry_price = float(position.avg_entry_price)

        row = [symbol, quantity, f"{avg_entry_price:.2f}"]

        if show_price_percentage_change:
            current_price = get_current_price(symbol)  # Replace with your actual method to get current price
            if current_price is None:  # Skip to next symbol if current price is None
                continue
            percentage_change = ((current_price - avg_entry_price) / avg_entry_price) * 100
            row.append(f"{percentage_change:.2f}%")

        table_data.append(row)

    table_str = tabulate(table_data, headers=headers, tablefmt="grid")
    title = "Currently Owned Positions to Sell for a Profit:"
    full_output = f"{title}\n\n{table_str}"
    print(full_output)
    return full_output

def print_and_share_positions(api2, show_price_percentage_change=False):
    table_str = print_positions(api2, show_price_percentage_change)
    content = (f"Here are the current stock market positions that I own "
               f"and that I need your help with to try to sell for a profit:\n{table_str}. "
               f"Just remember these owned stock market positions in your memory and no questions are asked about "
               f"these owned positions at this time. If there are no positions here, then we do not"
               f"currently own any positions.")
    organized_response(content, "positions")

def submit_buy_order(symbol, quantity):
    # Get the current time in Eastern Time
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    current_time = now.time()

    now = datetime.now(pytz.timezone('US/Eastern'))
    current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")

    # Define the allowed time ranges for the function to operate
    trading_start1 = time2(4, 34)
    trading_end1 = time2(5, 34)
    trading_start2 = time2(10, 15)
    trading_end2 = time2(11, 15)

    # Check if the current time is within the allowed trading hours
    if (trading_start1 <= current_time <= trading_end1) or (trading_start2 <= current_time <= trading_end2):
        account_info = api2.get_account()
        cash_available = float(account_info.cash)
        current_price = get_current_price(symbol)
        if current_price is None:
            # Skip order submission if current price is not found
            return

        # Define the market hours
        pre_market_start = time2(4, 0)
        pre_market_end = time2(9, 30)
        market_start = time2(9, 30)
        market_end = time2(16, 0)
        post_market_start = time2(16, 0)
        post_market_end = time2(20, 0)

        # Check if the market is open or if it is pre/post market
        if pre_market_start <= current_time < market_start or market_end <= current_time < post_market_end:
            # Extended hours: Pre-market or Post-market
            order = {
                'symbol': symbol,
                'qty': quantity,
                'side': 'buy',
                'type': 'limit',
                'time_in_force': 'day',
                'limit_price': current_price,  # Set the limit price as the current price
                'extended_hours': True  # Set to true for extended hours trading
            }
        elif market_start <= current_time < market_end:
            # Regular market hours
            order = {
                'symbol': symbol,
                'qty': quantity,
                'side': 'buy',
                'type': 'market',
                'time_in_force': 'day'
            }
        else:
            logging.info(f" {current_time_str} , The market is currently closed. No buy order was submitted for {symbol}. ")
            print(f"The market is currently closed. No buy order was submitted for {symbol}. ")
            return

        # Submit the order
        # (**order) is correct here
        api2.submit_order(**order)
        logging.info(f" {current_time_str} , Bought {quantity} shares of {symbol} at ${current_price:.2f}")

        print("")
        print(f" {current_time_str} , Bought {quantity} shares of {symbol} at {current_price}")
        print("")
        with open(csv_filename, mode='a', newline='') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csv_writer.writerow(
                {'Date': current_time_str, 'Buy': 'Buy', 'Quantity': quantity, 'Symbol': symbol,
                 'Price Per Share': current_price})
        # Add the symbol to the purchased_today dictionary
        purchased_today[symbol] = True
    else:
        print(f"The buy order was not sent for {symbol}. We are outside profit trading strategy hours. ")
        logging.info(f" {current_time_str} , The buy order was not sent for {symbol}. We are outside profit trading "
                     f"strategy hours. ")


def submit_sell_order(symbol, quantity):
    account_info = api2.get_account()
    day_trade_count = account_info.daytrade_count

    current_price = get_current_price(symbol)

    now = datetime.now(pytz.timezone('US/Eastern'))
    current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")

    if current_price is None:
        # Skip order submission if current price is not found
        return

    try:
        position = api2.get_position(symbol)
    except Exception as e:
        logging.error(f" {current_time_str} , No sell order was sent for {symbol}. We do not currently own this "
                      f"position: {e}")
        print(f"No sell order was sent for {symbol}. We do not currently own this position: {e}")
        return

    if position.qty != '0':
        bought_price = float(position.avg_entry_price)

        # Check if the market is open or if it is pre/post market
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)

        now = datetime.now(pytz.timezone('US/Eastern'))
        current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")

        pre_market_start = time2(4, 0)
        pre_market_end = time2(9, 30)

        market_start = time2(9, 30)
        market_end = time2(16, 0)

        post_market_start = time2(16, 0)
        post_market_end = time2(20, 0)

        if pre_market_start <= now.time() < market_start or market_end <= now.time() < post_market_end:
            # Extended hours: Pre-market or Post-market
            order = {
                'symbol': symbol,
                'qty': quantity,
                'side': 'sell',
                'type': 'limit',
                'time_in_force': 'day',
                'limit_price': current_price,  # Set the limit price as the current price
                'extended_hours': True  # Set to true for extended hours trading
            }
        elif market_start <= now.time() < market_end:
            # Regular market hours
            order = {
                'symbol': symbol,
                'qty': quantity,
                'side': 'sell',
                'type': 'market',
                'time_in_force': 'day'
            }
        else:
            logging.info(f" {current_time_str} , The market is currently closed. No sell order was submitted for {symbol}.")
            print(f"The market is currently closed. No sell order was submitted for {symbol}.")
            return

        # submit sell order
        # (**order) is correct here
        if day_trade_count < 3 and current_price and current_price >= bought_price + 0.01:
            api2.submit_order(**order)
            logging.info(f" {current_time_str} , Sold {quantity} shares of {symbol} at ${current_price:.2f}")
            print(f"Sold {quantity} shares of {symbol} at ${current_price:.2f}")
            with open(csv_filename, mode='a', newline='') as csv_file:
                csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                csv_writer.writerow(
                    {'Date': current_time_str, 'Sell': 'Sell', 'Quantity': quantity, 'Symbol': symbol,
                     'Price Per Share': current_price})
        else:
            logging.info(f" {current_time_str} , No order was submitted due to day trading limit or insufficient "
                         f"price increase.")
            print(f"No order was submitted due to day trading limit or insufficient price increase.")
    else:
        logging.info(f" {current_time_str} , You don't own any shares of {symbol}, so no sell order was submitted.")
        print(f"You don't own any shares of {symbol}, so no sell order was submitted.")


def sell_yesterdays_purchases():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)

    now = datetime.now(pytz.timezone('US/Eastern'))
    current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")
    
    account = api2.get_account()
    positions = api2.list_positions()

    today = now.date()
    for position in positions:
        symbol = position.symbol
        current_price = get_current_price(symbol)
        if current_price is None:  # Skip to next symbol if current price is None
            continue
        bought_price = float(position.avg_entry_price)

        # Check if the symbol is not in the purchased_today dictionary
        if symbol not in purchased_today:
            # Check if the last trade date is not today
            if current_price is None:  # Skip to next symbol if current price is None
                continue
            if current_price >= bought_price + 0.01:
                quantity = float(position.qty)
                submit_sell_order(symbol, quantity)
                logging.info(f" {current_time_str} , Sold {quantity} shares of {symbol} at ${current_price:.2f}")

def clear_purchased_today():
    global purchased_today
    purchased_today = {}

    now = datetime.now(pytz.timezone('US/Eastern'))
    current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")

    print("purchased_today dictionary variable has been cleared. ")
    logging.info(f" {current_time_str} , purchased_today dictionary variable has been cleared. ")

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
    market_open_time = time2(4, 0)
    market_close_time = time2(20, 0)

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
        print("Stockbot only works Monday through Friday: 4:00 am - 8:00 pm Eastern Time.")
        print("Stockbot begins watching stock prices early at 4:00 am Eastern Time.")
        print("Waiting until Stock Market Hours to begin the Stockbot Trading Program.")
        print("\n")
        print("\n")
        print("\n")
        print_account_balance_change()
        print("\n")
        time.sleep(60)  # Sleep for 1 minute and check again. Keep this under the p in print.

def stop_scheduler_thread_if_stock_market_is_closed():
    # Check if the current time is within the stock market hours
    # Set the stock market open and close times
    market_open_time = time2(4, 0)
    market_close_time = time2(20, 0)

    while True:
        # Get the current time in Eastern Time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        current_time = now.time()
        current_time_str = now.strftime("EST | %I:%M:%S %p | %m-%d-%Y |")

        # Check if the current time is within market hours
        if now.weekday() <= 4 and market_open_time <= current_time <= market_close_time:
            break

        print("\n")
        print(f"{current_time_str}")
        print("\n")
        print("Task Scheduler is waiting for the Stock Market trading hours to start running. ")
        print("Task scheduling sell orders at profit selling strategy times. ")
        print("Working 4:00 - 20:00 ")
        print("\n")
        time.sleep(60)

def scheduler_thread():
    stop_scheduler_thread_if_stock_market_is_closed()
    # Schedule tasks once at the start
    # these times are in the local time zone for your computer
    # I will set these times to the Central Time Zone.
    schedule.every().day.at("03:00").do(clear_purchased_today)  # Run at 04:00 am every day
    schedule.every().day.at("03:01").do(clear_purchased_today)  # double check the run at 04:01
    schedule.every().day.at("08:31").do(sell_yesterdays_purchases)
    schedule.every().day.at("10:55").do(sell_yesterdays_purchases)
    schedule.every().day.at("14:59").do(sell_yesterdays_purchases)

    while True:
        # Get the current time in Central Time
        eastern = pytz.timezone('US/Central')
        now = datetime.now(eastern)

        current_time_str = now.strftime("CST | %I:%M:%S %p | %m-%d-%Y |")

        print("\n")
        print("--------------------------------------------------------------------------")
        print(f"{current_time_str}")
        print(f"Task Scheduler: scheduling sell orders at profit selling strategy times. ")
        print("--------------------------------------------------------------------------")
        print("\n")
        # below is the debug code to print status messages
        # print("Scheduler tasks thread is successfully running. ")
        # logging.info("Scheduler tasks thread is successfully running. ")
        schedule.run_pending()

        time.sleep(60)  # Check for scheduled tasks every 59 seconds

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

            print_and_share_positions(api2, show_price_percentage_change=True)

            for symbol in symbols:
                try:
                    previous_price = get_14_days_price(symbol)
                    current_price = get_current_price(symbol)
                    if current_price is None:  # Skip to next symbol if current price is None
                        continue
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
                    now = datetime.now(pytz.timezone('US/Eastern'))
                    compact_current_time_str = now.strftime("EST %I:%M:%S %p ")
                    print(compact_current_time_str)
                    print("--------------------------")
                    print("\n")
                    logging.info(f" {current_time_str} , Signal: {signal}")
                    print("Waiting 15 seconds to not exceed API rate limits and to keep the video card at a colder "
                          "temperature. ")
                    time.sleep(15)  # Add a 1-second delay

                except Exception as e:     # this is under the t in try
                    logging.error(f"Error: {e}")
                    time.sleep(5)

            print("\n")
            print_account_balance_change()
            print("\n")
            print("Waiting 25 seconds ")
            print("\n")
            time.sleep(25)  # keep this under the "f" in for symbol

        except Exception as e:     # this is under the t in try
            logging.error(f"Error in main loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    scheduler_thread_instance = threading.Thread(target=scheduler_thread)
    scheduler_thread_instance.start()

    clear_purchased_today()
    print("\n")
    print("Scheduler tasks thread successfully started")
    print("\n")
    logging.info("Scheduler tasks thread successfully started")

    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(5)
