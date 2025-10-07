"""
my_keys.py - List registered Bittensor wallets for a given netuid.

This script scans the default Bittensor wallet directory (~/.bittensor/wallets),
collects all cold-key wallets whose names start with “c” or “x”, queries the
local subtensor metagraph for the specified netuid (default 117), and prints
the wallet names together with their UID on that subnet.

Usage:
    python my_keys.py
"""


import bittensor as bt
import os

def get_coldkey_wallets_for_path(path: str) -> list[bt.Wallet]:
    """Get all coldkey wallet names from path."""
    try:
        wallet_names = next(os.walk(os.path.expanduser(path)))[1]
        # sort wallet names alphabetically (but c123 after c23)
        wallet_names = sorted(wallet_names, key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else x[1:]))
        return [bt.Wallet(path=path, name=name) for name in wallet_names if name.startswith('c') or name.startswith('x')]
    except StopIteration:
        # No wallet files found.
        wallets = []
    return wallets

def get_registered_wallets(wallets, netuid) -> list[bt.Wallet]:
    """Get all registered coldkey wallets."""
    s = bt.subtensor("local")
    m = s.metagraph(netuid=netuid)
    registered_wallets = [(wallet, m.hotkeys.index(wallet.hotkey.ss58_address)) for wallet in wallets if wallet.hotkey.ss58_address in m.hotkeys]
    return registered_wallets

def print_wallets(wallets):
    """Print wallet names and their ss58 addresses."""
    for (wallet, uid) in wallets:
        print(f"Wallet Name: {wallet.name}, Netuid: {uid}")

wallets = get_coldkey_wallets_for_path("~/.bittensor/wallets")
registered_wallets = get_registered_wallets(wallets, netuid=117)

print_wallets(registered_wallets)