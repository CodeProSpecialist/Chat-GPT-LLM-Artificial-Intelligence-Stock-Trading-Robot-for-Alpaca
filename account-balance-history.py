import os
import datetime
from tkinter import *
from tkcalendar import Calendar
from alpaca_trade_api import REST

# Configure Alpaca API
API_KEY_ID = os.getenv('APCA_API_KEY_ID')
API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Initialize Alpaca API
api = REST(API_KEY_ID, API_SECRET_KEY, API_BASE_URL)

def get_account_balance(date):
    # Get portfolio history for the specified date
    balance = api.get_portfolio_history(
        timeframe='1D',
        date_start=date.strftime("%Y-%m-%d")
    ).equity

    return balance

def get_selected_balance():
    selected_date = calendar.selection_get()
    selected_balance = get_account_balance(selected_date)
    balance_label.config(text=f"Balance for {selected_date}: ${selected_balance}", font=("Courier", 16, "bold"))

root = Tk()
root.title("Account Balance History")
root.geometry("1024x800")  # Increase width to 1000

calendar = Calendar(root)
calendar.pack(padx=10, pady=10)

select_button = Button(root, text="Select", command=get_selected_balance)
select_button.pack(pady=10)

balance_label = Label(root, text="", font=("Courier", 16, "bold"))  # Set font size to 16 and bold
balance_label.pack(pady=10)

root.mainloop()
