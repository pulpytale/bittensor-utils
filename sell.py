"""
Automated Bittensor subnet-price watcher & unstaker.

Logic overview:
- Polls the live TAO price of subnet 117 on a local subtensor in a tight loop.
- Two price thresholds govern behavior:
  - 0.0015 TAO: minimum interest level; prints status only every 200 loops.
  - 0.0020 TAO: trigger level; executes an unstake action.
- When the trigger is hit:
  - Unstakes exactly 10 TAO from validator 5H4BrsKdARdeWr5koKjru35dEVB9a35c7gToykhaCzYaDeaT.
  - Transfers proceeds back to coldkey wallet “c0”.
- Global counters:
  - cnt: total loop iterations.
  - sell_cnt: successful unstake operations.
- All blockchain interactions use the local subtensor and btcli via pexpect.
"""

import bittensor as bt
import pexpect
import time

s = bt.subtensor("local")

def get_subnet_price(netuid = 117):
    price = s.get_subnet_price(netuid)
    return price

cnt = 0
buy_cnt = 0
sell_cnt = 0

wallet = bt.wallet(name='c0')
balance = s.get_balance(wallet.coldkeypub.ss58_address)

def unstake():
    global balance
    global sell_cnt
    child = pexpect.spawn("btcli stake remove --wallet.name c0 --netuid 117 --unsafe -in 5H4BrsKdARdeWr5koKjru35dEVB9a35c7gToykhaCzYaDeaT --amount 10 --quiet --subtensor.network local")
    child.expect("Would you like to continue")
    child.sendline("y")
    child.expect("Enter your password")
    child.sendline("ChainDude321!a")
    child.interact()
    new_balance = s.get_balance(wallet.coldkeypub.ss58_address)
    if new_balance > balance:
        sell_cnt += 1
        print(f"Sell successful! New balance: {new_balance} TAO, total sells: {sell_cnt}")
        balance = new_balance

while True:
    try:
        price = get_subnet_price(117)
        if float(price) > 0.0015:
            if cnt % 200 == 0:
                print(f"Current subnet price is {price} TAO, which is above threshold of 0.0015 TAO. Not Selling.")
            cnt += 1
            if float(price) > 0.0020:
                print(f"Current subnet price is {price} TAO, which is above 0.0019 TAO. Unstaking now...")
                unstake()
            time.sleep(0.05)
            continue
        time.sleep(0.1)
    except Exception as e:
        print(f"Exception occurred: {e}")
        time.sleep(0.1)