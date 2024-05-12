
I recommend downloading the newest version of this Python Robot. 
New Updates and more features were added on May 12, 2024. 

![Screenshot from 2024-05-12 16-34-47](https://github.com/CodeProSpecialist/Chat-GPT-LLM-Artificial-Intelligence-Stock-Trading-Robot-for-Alpaca/assets/111866070/2a652409-fc80-4148-a296-cf5b62e712ec)


It is recommended to first install Anaconda3 to setup a Python 3 virtual environment. 

Just run the following commands: 

sh install.sh

For this version of Ollama to work best, 
do not install Ollama with docker or with snap. 

Install Ollama using the install download link on 
the official Ollama website:     https://ollama.com/

Run the following command for Ollama to download the llama3:8b-instruct-q4_0 GPT model: 

ollama run llama3:8b-instruct-q4_0

python3 python-brain-model-trading-robot.py


note: the raspberry pi can work with: 
tinyllama:1.1b-chat-v1-q2_K

ollama run tinyllama:1.1b-chat-v1-q2_K


----------------------------------------------------

Disclaimer:

This software is not affiliated with or endorsed Alpaca Securities, LLC. It aims to be a valuable tool for stock market trading, but all trading involves risks. Use it responsibly and consider seeking advice from financial professionals.

Ready to elevate your trading game? Download the Artificial-Intelligence-Stock-Trading-Robot, and get started today!

Important: Don't forget to regularly update your list of stocks to buy and keep an eye on the market conditions. Happy trading!

Remember that all trading involves risks. The ability to successfully implement these strategies depends on both market conditions and individual skills and knowledge. As such, trading should only be done with funds that you can afford to lose. Always do thorough research before making investment decisions, and consider consulting with a financial advisor. This is use at your own risk software. This software does not include any warranty or guarantees other than the useful tasks that may or may not work as intended for the software application end user. The software developer shall not be held liable for any financial losses or damages that occur as a result of using this software for any reason to the fullest extent of the law. Using this software is your agreement to these terms. This software is designed to be helpful and useful to the end user.

Place your alpaca code keys in the location: /home/name-of-your-home-folder/.bashrc Be careful to not delete the entire .bashrc file. Just add the 4 lines to the bottom of the .bashrc text file in your home folder, then save the file. .bashrc is a hidden folder because it has the dot ( . ) in front of the name. Remember that the " # " pound character will make that line unavailable. To be helpful, I will comment out the real money account for someone to begin with an account that does not risk using real money. The URL with the word "paper" does not use real money. The other URL uses real money. Making changes here requires you to reboot your computer or logout and login to apply the changes.

The 4 lines to add to the bottom of .bashrc are:

export APCA_API_KEY_ID='zxzxzxzxzxzxzxzxzxzxz'

export APCA_API_SECRET_KEY='zxzxzxzxzxzxzxzxzxzxzxzxzxzxzxzxzxzxzxzx'

#export APCA_API_BASE_URL='https://api.alpaca.markets'

export APCA_API_BASE_URL='https://paper-api.alpaca.markets'
