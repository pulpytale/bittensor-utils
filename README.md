# Bittensor Utils

A small set of Python utilities to monitor Bittensor subnet prices and automate staking/unstaking, plus wallet discovery helpers.

Included scripts:
- <mcfile name="auto_buy_alpha.py" path="/Users/imac/Documents/projects/bittensor-utils/auto_buy_alpha.py"></mcfile>
  - Watches a destination subnet price and automatically adds stake when the price falls below a TAO threshold.
  - Supports custom network (finney/test/local/mainnet), safe staking checks, partial staking, and optional waits for inclusion/finalization.
- <mcfile name="sell.py" path="/Users/imac/Documents/projects/bittensor-utils/sell.py"></mcfile>
  - Simple price watcher for local subtensor that unstakes a fixed amount when a trigger is hit.
  - Uses btcli via pexpect; contains hardcoded wallet, validator address, and password (for demo only).
- <mcfile name="my_keys.py" path="/Users/imac/Documents/projects/bittensor-utils/my_keys.py"></mcfile>
  - Lists locally stored coldkey wallets and shows their registered UID on a target netuid.

Requirements
- Python 3.10+
- Packages in <mcfile name="requirements.txt" path="/Users/imac/Documents/projects/bittensor-utils/requirements.txt"></mcfile> (bittensor, pexpect)
- A configured Bittensor environment (wallets, hotkeys, and access to a subtensor network)

Setup
- Create and activate a virtualenv (recommended)
- Install dependencies: pip install -r requirements.txt

Usage
- Auto-buy stake (recommended script)
  - Example:
    - python auto_buy_alpha.py --wallet.name c0 --wallet.hotkey default --network finney \
      --amount-tao 0.5 --threshold-tao 0.0017 --netuid 117 --interval 60 --max-swaps 1
  - Common flags:
    - --wallet.name, --wallet.hotkey: wallet identifiers
    - --network: finney | test | local | mainnet (default: finney)
    - --origin-netuid: netuid to report existing stake on (default: 0)
    - --netuid: target netuid to stake (default: 117)
    - --amount-tao: TAO to stake per operation (required)
    - --threshold-tao: price trigger (default: 0.0017)
    - --interval: polling interval seconds (default: 60)
    - --max-swaps: number of stake ops before exit (0 = run forever; default: 1)
    - --dry-run: simulate without submitting
    - --safe-staking, --allow-partial, --rate-tolerance: safety controls
    - --wait-for-finalization, --no-wait-for-inclusion: extrinsic wait behavior

- Unstake on local (demo)
  - python sell.py
  - WARNING: This script is hardcoded for a local network, wallet name "c0", a validator address, and a plaintext password. Do not use as-is in production.

- List registered wallets
  - python my_keys.py

Security & Safety
- Never commit or use plaintext passwords. The demo in sell.py is for local testing only; remove password usage or source it securely (e.g., from environment variables or a keyring).
- Staking/unstaking transfers real value. Test with --dry-run and/or a local network first.

Notes
- Defaults target netuid 117 and threshold 0.0017 TAO in auto_buy_alpha.py; adjust to fit your strategy.
- Network connectivity and wallet availability are required; ensure your wallet files exist and the hotkey loads successfully.

Future additions
- More scripts will be added over time as the toolkit evolves.