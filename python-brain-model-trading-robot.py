import os
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
import pandas_market_calendars as mcal
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

global close_prices, time_period, csv_writer, csv_filename, fieldnames, eastern, nyse, market_holidays

purchased_today = {}

# Initialize NYSE calendar
nyse = mcal.get_calendar('NYSE')
market_holidays = nyse.holidays().holidays

# Initialize US Eastern Time
eastern = pytz.timezone('US/Eastern')

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


def is_market_open():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    # Convert to Eastern Time
    now_eastern = now.astimezone(eastern)

    # Initialize NYSE calendar
    nyse = mcal.get_calendar('NYSE')
    market_holidays = nyse.holidays().holidays

    # Check if the current time is a trading day and within trading hours
    if now_eastern.weekday() >= 5 or now_eastern.date() in market_holidays:
        return False

    market_open_time = time2(4, 0)  # 4:00 AM ET
    market_close_time = time2(20, 0)  # 8:00 PM ET

    return market_open_time <= now_eastern.time() <= market_close_time


def is_daytime_market_hours():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    # Convert to Eastern Time
    now_eastern = now.astimezone(eastern)

    # Initialize NYSE calendar
    nyse = mcal.get_calendar('NYSE')
    market_holidays = nyse.holidays().holidays

    # Check if the current time is a trading day and within daytime trading hours
    if now_eastern.weekday() >= 5 or now_eastern.date() in market_holidays:
        return False

    market_open_time = time2(9, 30)  # 9:30 AM ET
    market_close_time = time2(16, 0)  # 4:00 PM ET

    return market_open_time <= now_eastern.time() <= market_close_time


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
    while date.weekday() > calendar.FRIDAY or date in market_holidays.holidays:
        date -= timedelta(days=1)
    return date


def print_account_balance_change():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)

    # THIS CODE WORKS CORRECTLY. NOTHING SHOWS THE DAY AFTER A HOLIDAY
    # NOTHING SHOWS THE DAY AFTER THE MARKET WAS CLOSED.
    # Check if the market is within daytime market hours
    if not is_daytime_market_hours():
        print("The percentage change information is only available 9:30am - 4:00pm Eastern Time, Monday - Friday.")
        return

    # Get today's date in Eastern Time
    today = now.date()

    # Adjust today to the last trading day if today is Saturday, Sunday, or a holiday
    if today.weekday() == calendar.SATURDAY:
        today -= timedelta(days=1)
    elif today.weekday() == calendar.SUNDAY:
        today -= timedelta(days=2)

    # Ensure today is not a holiday using pandas_market_calendars
    if today in market_holidays.holidays:
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
            print(f"{label}: No percentage change data available 7, 14, or 30 days ago in your portfolio. "
                  f"Possibly the Stock Market was closed for a holiday 7, 14, or 30 days ago. "
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


def trading_robot(symbol, x, y):
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

    # Determine price trend based on the day of the week
    if day_of_week in ["Thursday", "Friday"]:
        price_trend = "increasing"
    elif day_of_week in ["Monday", "Tuesday", "Wednesday"]:
        price_trend = "decreasing"
    else:
        price_trend = "stagnant or decreasing"

    # Determine market trend based on the month
    if month in ["May", "June", "July", "November", "December"]:
        market_trend_month = "bullish"
    elif month == "February":
        market_trend_month = "bullish sometimes"
    else:
        market_trend_month = "bearish or stagnant"

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
        market_trend = 'bullish'
    else:
        market_trend = 'bearish'

    # Retrieve account information
    account_info = api2.get_account()
    account_balance = float(account_info.equity)
    available_cash = float(account_info.cash)
    day_trade_count = api2.get_account().daytrade_count

    # the following code will print owned positions and their percentage change.
    table_str = print_positions_in_text_only(api2, show_price_percentage_change=True)
    # Debug print the account information
    # print(f"Account Balance: ${account_balance:.2f}")
    # print(f"Available Cash: ${available_cash:.2f}")
    # print("Day Trades Remaining:", day_trades_remaining)

    # content message includes account information for making trading decisions

    content = (
        f"Decision assistance required: "
        f"Respond with **buy {symbol}** to suggest a purchase, "
        f"**sell {symbol}** to recommend selling, "
        f"or **hold {symbol}** to advise holding. "
        f"Analyze all technical indicators for informed decisions. "
        f"Your role as a stock market trading assistant is crucial here. "
        f"Buying early during the times range of 4:34-5:34 is mandatory as a default priority, "
        f"especially during bear market trends. We never buy anything on Monday. "
        f"Current time: {now.strftime('%H:%M:%S')}. "
        f"Preferred buying times: 4:34-5:34 and 10:15-11:15. "
        f"Selling times: 9:31-9:38, 15:30-15:59, and 19:30-19:59. "
        f"Exception: No buying 4:00-10:14 unless price < yesterday's close. "
        f"On Tuesdays, no buying 4:00-10:14. "
        f"No trading after 19:59 or when the market is closed. "
        f"Sell for ≥ 0.25% profit anytime. "
        f"{symbol} changed by {x}% in the last {y} days. "
        f"RSI: {rsi:.2f}, 50-day MA: {short_ma:.2f}, 100-day MA: {long_ma:.2f}. "
        f"Market trend: {market_trend}. "
        f"Price changed by {fourteen_days_change:.2f}% in the last 14 days. "
        f"Current Volume: {today_new_volume:.2f}, Average Volume: {avg_volume:.2f}. "
        f"Buy when Volume ≤ Average Volume, sell when RSI > 70 or Volume ≥ Average Volume. "
        f"Criteria: Buy if RSI < 30, 50-day MA > 200-day MA, and price ↑ in 14 days. "
        f"Sell if RSI > 70, 50-day MA < 200-day MA, and price ↓ in 14 days. "
        f"Bollinger Bands: Upper: {upper_band_value:.2f}, Middle: {middle_band_value:.2f}, Lower: {lower_band_value:.2f}. "
        f"Buy ≤ Lower Band, sell ≥ Upper Band. "
        f"Yesterday's close: {yesterday_close:.2f}, Today's open: {today_open:.2f}, Current price: {today_current:.2f}. "
        f"ATR low price: {atr_low_price:.2f}, ATR high price: {atr_high_price:.2f}. "
        f"Buy near ATR low, sell near ATR high. "
        f"Date: {now.strftime('%A, %B %d, %Y')}. "
        f"Today is {day_of_week}, prices typically {price_trend}. "
        f"Month: {month}, market usually {market_trend_month}. "
        f"Default sell time during bear markets: 11:40-12:10. "
        f"On Monday-Wednesday, sell 11:40-12:10. "
        f"On Friday, sell all 11:40-12:10 due to weekend decline. "
        f"No buying Fridays 11:16-20:00 due to weekend decline. "
        f"Account Balance: {account_balance:.2f}, Available Cash: {available_cash:.2f}, "
        f"Day Trades Left: {day_trade_count} of 3 in 5 days. "
        f"Max 3 day trades per 5 days; buy and sell same day. "
        f"Owned Positions: {table_str}. "
        f"Goal: Sell all today for 3-5% profit. "
        f"Buy when RSI and price rise, sell immediately when both RSI and price fall after rising to "
        f"3-5% profit per owned position. "
        f"Your response should be formatted as: "
        f"**buy {symbol}**, **sell {symbol}**, or **hold {symbol}**. "
        f"Explain reasoning briefly after. "
    )

    decision = organized_response(content, symbol)
    return decision


def organized_response(content, symbol):
    messages = [{'role': 'user', 'content': content}]
    response = chat('llama3:8b-instruct-q4_0', messages=messages)
    response_content = response['message']['content'].strip().lower()

    # Debug prints
    # print("\nContent:\n", content, "\n")    # comment out after finished debugging
    # print("\nMessages:\n", messages, "\n")   # comment out after finished debugging
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
        return f"No buy, sell, or hold signal was recognized. "


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


def print_positions_in_text_only(api2, show_price_percentage_change=False):
    positions = api2.list_positions()

    formatted_output = []

    for position in positions:
        symbol = position.symbol
        quantity = position.qty
        avg_entry_price = float(position.avg_entry_price)

        row = []

        # Symbol and Quantity
        row.append(f"{symbol} quantity: {quantity}")

        # Avg Entry Price
        row.append(f"{symbol} Avg Entry Price: {avg_entry_price:.2f}")

        if show_price_percentage_change:
            current_price = get_current_price(symbol)  # Replace with your actual method to get current price
            if current_price is None:  # Skip to next symbol if current price is None
                continue
            percentage_change = ((current_price - avg_entry_price) / avg_entry_price) * 100
            row.append(f"{symbol} percentage change: {percentage_change:.2f}%")

        # Append formatted row to output
        formatted_output.append(" | ".join(row))

    # Return the formatted output as a single string
    return " ".join(formatted_output)

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
            logging.info(
                f" {current_time_str} , The market is currently closed. No buy order was submitted for {symbol}. ")
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
            logging.info(
                f" {current_time_str} , The market is currently closed. No sell order was submitted for {symbol}.")
            print(f"The market is currently closed. No sell order was submitted for {symbol}.")
            return

        # sell at + 0.03% or greater profit to allow selling with market sell orders for profit
        # current_price >= bought_price * 1.0003
        # 0.03% daily profit was recommended by artificial intelligence as the
        # average daily profit for the S&P 500.
        # Sell stocks if the current price is more than 0.03% higher than the purchase price.
        # submit sell order
        # (**order) is correct here
        if day_trade_count < 3 and current_price >= bought_price * 1.0003:
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

    # Add logging for the start of the function
    logging.info(f"{current_time_str} currently running sell_yesterdays_purchases function. ")
    print(f"{current_time_str} currently running sell_yesterdays_purchases function. ")

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
            # sell at + 0.03% or greater profit to allow selling with market sell orders for profit
            # current_price >= bought_price * 1.0003
            # 0.03% daily profit was recommended by artificial intelligence as the
            # average daily profit for the S&P 500.
            # Sell stocks if the current price is more than 0.03% higher than the purchase price.
            if current_price >= bought_price * 1.0003:
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
    while True:
        # Get the current time in Eastern Time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)

        # Check if the current time is within market hours
        if is_market_open():
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
    while True:
        # Get the current time in Eastern Time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)

        current_time_str = now.strftime("EST | %I:%M:%S %p | %m-%d-%Y |")

        # Check if the current time is within market hours
        if is_market_open():
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
    
    # Schedule tasks once at the start in Central Time Zone
    schedule.every().day.at("03:00").do(clear_purchased_today)  # Run at 03:00 am (CST) every day
    schedule.every().day.at("03:01").do(clear_purchased_today)  # Double check run at 03:01 (CST)
    schedule.every().day.at("14:58").do(sell_yesterdays_purchases)  # Run at 14:58 pm (CST) every day
    schedule.every().day.at("14:59").do(sell_yesterdays_purchases)  # Double check run at 14:59 pm (CST)
    schedule.every().day.at("18:58").do(sell_yesterdays_purchases)  # Run at 18:58 pm (CST) every day
    schedule.every().day.at("18:59").do(sell_yesterdays_purchases)  # Double check run at 18:59 pm (CST)

    while True:
        # Get the current time in Central Time
        central = pytz.timezone('US/Central')
        now = datetime.now(central)

        current_time_str = now.strftime("CST | %I:%M:%S %p | %m-%d-%Y |")

        print("\n")
        print("--------------------------------------------------------------------------")
        print(f"{current_time_str}")
        print(f"Task Scheduler: scheduling sell orders at profit selling strategy times. ")
        print("--------------------------------------------------------------------------")
        print("\n")
        
        # Debug code to print status messages
        # print("Scheduler tasks thread is successfully running.")
        # logging.info(f"Scheduler tasks thread is successfully running. {current_time_str}")
        
        schedule.run_pending()
        time.sleep(60)  # Check for scheduled tasks every 60 seconds


def adjust_quantity(quantity, cash_balance, current_price):
    """
    Adjusts the trading quantity based on predefined rules.

    Returns the adjusted quantity.
    """
    if quantity < 1:
        return 0
    elif quantity == 1 or quantity == 2:
        return quantity  # No change needed for quantity 1 or 2
    elif quantity >= 3:
        return 3


def main():
    symbols = get_stocks_to_trade()
    if not symbols:
        return

    while True:
        try:
            global market_holidays, holidays
            # Initialize NYSE calendar
            nyse = mcal.get_calendar('NYSE')
            market_holidays = nyse.holidays()

            now = datetime.now(pytz.timezone('US/Eastern'))
            current_time_str = now.strftime("Eastern Time | %I:%M:%S %p | %m-%d-%Y |")

            stop_if_stock_market_is_closed()  # comment this line to debug the Python code

            # Ensure holiday_list is the correct type
            if not hasattr(market_holidays, 'holidays'):
                raise AttributeError("holiday_list does not have attribute 'holidays'")

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

            print_positions(api2, show_price_percentage_change=True)

            for symbol in symbols:
                try:
                    previous_price = get_14_days_price(symbol)
                    current_price = get_current_price(symbol)
                    if current_price is None:  # Skip to next symbol if current price is None
                        continue
                    debug_print_14_days_prices = get_14_days_price(symbol)
                    x = calculate_percentage_change(current_price, previous_price)
                    y = 14
                    signal = trading_robot(symbol, x, y)
                    cash_balance = float(api2.get_account().cash)
                    quantity = int(cash_balance / current_price)

                    # Adjust quantity based on the adjust_quantity function settings.
                    quantity = adjust_quantity(quantity, cash_balance, current_price)

                    execute_trade(symbol, signal, quantity)
                    print(f"Symbol: {symbol}")
                    print(f"Current Price: {current_price}")
                    print(f"Decision: {signal}")
                    print("\n")
                    now = datetime.now(pytz.timezone('US/Eastern'))
                    compact_current_time_str = now.strftime("EST %I:%M:%S %p ")
                    print(compact_current_time_str)
                    print("--------------------------")
                    print("\n")
                    logging.info(f" {current_time_str} , Signal: {signal}")
                    print("Waiting 15 seconds to not exceed API rate limits and to keep the video card at a colder "
                          "temperature.")
                    time.sleep(15)  # keep this under the p in print.

                except Exception as e:      # this is under the t in try
                    logging.error(f"Error: {e}")
                    time.sleep(5)

            # Print account balance change at an appropriate place
            print("\n")
            print_account_balance_change()  # Replace with your actual function
            print("\n")
            print("Waiting 25 seconds ")
            print("\n")
            # sleep time is 25 seconds
            time.sleep(25)   # keep this under the "f" in for symbol


        except Exception as e:  # this is under the t in try ( the while true try )

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
