#!/usr/bin/env python3
"""Utility to automatically buy stake on a subnet when the price is favorable.

This script watches the Alpha price for a destination subnet (default 117) and, when the
price falls below a configured TAO threshold, issues an `add_stake` extrinsic to deposit
fresh stake from the wallet's coldkey balance into the destination subnet. The wallet and
amount to stake are provided by command line arguments.

Example usage:
    python support/auto_buy_subnet.py \
        --wallet.name my_wallet \
        --wallet.hotkey default \
        --network finney \
        --amount-tao 0.5 \
        --threshold-tao 0.001 \
        --netuid 117
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - imports for type checkers only
    import bittensor as bt
    from bittensor.utils.balance import Balance

DEFAULT_THRESHOLD = 0.0017  # TAO
DEFAULT_INTERVAL = 60.0  # seconds
DEFAULT_RATE_TOLERANCE = 0.025  # 2.5%
DEFAULT_NETWORK = "finney"


@dataclass
class Args:
    wallet_name: str
    wallet_hotkey: str
    network: str
    origin_netuid: int
    netuid: int
    amount_tao: float
    threshold_tao: float
    interval: float
    max_stakes: int
    dry_run: bool
    safe_staking: bool
    allow_partial: bool
    rate_tolerance: float
    wait_for_finalization: bool
    wait_for_inclusion: bool


def parse_args(argv: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor a subnet Alpha price and automatically add stake when it falls "
            "below the desired TAO threshold."
        )
    )
    parser.add_argument(
        "--wallet.name",
        dest="wallet_name",
        help="Name of the coldkey wallet",
    )
    parser.add_argument(
        "--wallet.hotkey",
        dest="wallet_hotkey",
        default="default",
        help="Hotkey name stored under the wallet",
    )
    parser.add_argument(
        "--network",
        default=DEFAULT_NETWORK,
        help="Subtensor network to target (e.g. finney, test, local, mainnet)",
    )
    parser.add_argument(
        "--origin-netuid",
        type=int,
        default=0,
        help="Optional netuid to monitor existing stake on (default: 0)",
    )
    parser.add_argument(
        "--netuid",
        type=int,
        default=117,
        dest="netuid",
        help="Netuid to stake on when conditions are met (default: 117)",
    )
    parser.add_argument(
        "--destination-netuid",
        type=int,
        dest="netuid",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--amount-tao",
        type=float,
        required=True,
        help="Amount of stake (in TAO) to add per successful interval",
    )
    parser.add_argument(
        "--threshold-tao",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Trigger price in TAO (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds between price checks (default: 60)",
    )
    parser.add_argument(
        "--max-swaps",
        type=int,
        default=1,
        help="Maximum number of stake operations before exiting (0 = run forever, default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only log what would happen without submitting extrinsics",
    )
    parser.add_argument(
        "--safe-staking",
        action="store_true",
        help="Enable Bittensor safe staking checks (stake_limit)",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow partial staking when safe staking tolerance would be exceeded",
    )
    parser.add_argument(
        "--rate-tolerance",
        type=float,
        default=DEFAULT_RATE_TOLERANCE,
        help="Maximum price ratio increase allowed when safe staking (default: 0.025 = 2.5%%)",
    )
    parser.add_argument(
        "--wait-for-finalization",
        action="store_true",
        help="Wait for block finalization before reporting success",
    )
    parser.add_argument(
        "--no-wait-for-inclusion",
        action="store_true",
        help="Return immediately after submitting the extrinsic (no inclusion wait)",
    )

    parsed = parser.parse_args(argv)

    if not parsed.wallet_name:
        parser.error("--wallet.name is required")
    if not parsed.wallet_hotkey:
        parser.error("--wallet.hotkey is required")
    if parsed.amount_tao <= 0:
        parser.error("--amount-tao must be greater than zero")
    if parsed.threshold_tao <= 0:
        parser.error("--threshold-tao must be greater than zero")
    if parsed.interval <= 0:
        parser.error("--interval must be greater than zero")
    if parsed.max_swaps < 0:
        parser.error("--max-swaps must be zero or a positive integer")
    if parsed.rate_tolerance < 0:
        parser.error("--rate-tolerance must be non-negative")

    return Args(
        wallet_name=parsed.wallet_name,
        wallet_hotkey=parsed.wallet_hotkey,
        network=parsed.network,
        origin_netuid=parsed.origin_netuid,
        netuid=parsed.netuid,
        amount_tao=parsed.amount_tao,
        threshold_tao=parsed.threshold_tao,
        interval=parsed.interval,
        max_stakes=parsed.max_swaps,
        dry_run=parsed.dry_run,
        safe_staking=parsed.safe_staking,
        allow_partial=parsed.allow_partial,
        rate_tolerance=parsed.rate_tolerance,
        wait_for_finalization=parsed.wait_for_finalization,
        wait_for_inclusion=not parsed.no_wait_for_inclusion,
    )


def load_wallet(bt_module, name: str, hotkey: str):
    wallet = bt_module.wallet(name=name, hotkey=hotkey)
    # Accessing the hotkey ensures the keyfile is loaded before we attempt to use it.
    try:
        _ = wallet.hotkey
    except Exception as err:  # pylint: disable=broad-except
        raise RuntimeError(f"Unable to load hotkey '{hotkey}' from wallet '{name}': {err}") from err
    return wallet


def format_balance(balance: Optional[Balance]) -> str:
    if balance is None:
        return "n/a"
    return f"{balance.tao:.9f} {balance.unit}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        import bittensor as bt
        from bittensor.utils.balance import Balance
    except Exception as err:  # pylint: disable=broad-except
        raise RuntimeError(f"Unable to import bittensor dependencies: {err}") from err

    bt.logging.info(
        f"Starting auto-buy watcher (monitoring netuid {args.origin_netuid} → staking netuid {args.netuid}, "
        f"threshold {args.threshold_tao:.6f} TAO)"
    )

    wallet = load_wallet(bt, args.wallet_name, args.wallet_hotkey)
    hotkey_ss58 = wallet.hotkey.ss58_address
    bt.logging.info(f"Using hotkey {hotkey_ss58}")

    subtensor = bt.subtensor(network=args.network)
    bt.logging.info(f"Connected to network '{args.network}'")

    target_amount = Balance.from_tao(args.amount_tao, netuid=args.netuid)

    stakes_completed = 0
    while args.max_stakes == 0 or stakes_completed < args.max_stakes:
        coldkey_balance: Optional[Balance] = None
        origin_stake: Optional[Balance] = None
        destination_stake: Optional[Balance] = None

        try:
            price = subtensor.get_subnet_price(netuid=args.netuid)
        except Exception as err:  # pylint: disable=broad-except
            bt.logging.error(f"Failed to fetch subnet price: {err}")
            time.sleep(args.interval)
            continue

        bt.logging.info(
            f"Subnet {args.netuid} price: {price.tao:.9f} TAO (threshold {args.threshold_tao:.9f} TAO)"
        )

        try:
            coldkey_balance = subtensor.get_balance(wallet.coldkeypub.ss58_address)
        except Exception as err:  # pylint: disable=broad-except
            bt.logging.error(f"Failed to fetch coldkey balance: {err}")

        try:
            origin_stake = subtensor.get_stake_for_hotkey(
                hotkey_ss58=hotkey_ss58,
                netuid=args.origin_netuid,
            )
        except Exception as err:  # pylint: disable=broad-except
            bt.logging.error(
                f"Unable to fetch stake on origin netuid {args.origin_netuid}: {err}"
            )

        try:
            destination_stake = subtensor.get_stake_for_hotkey(
                hotkey_ss58=hotkey_ss58,
                netuid=args.netuid,
            )
        except Exception as err:  # pylint: disable=broad-except
            bt.logging.error(
                f"Unable to fetch stake on destination netuid {args.netuid}: {err}"
            )

        bt.logging.info(
            f"Balances — coldkey {format_balance(coldkey_balance)} | "
            f"origin netuid {args.origin_netuid} stake {format_balance(origin_stake)} | "
            f"target netuid {args.netuid} stake {format_balance(destination_stake)}"
        )

        if price.tao <= args.threshold_tao:
            bt.logging.info(
                f"Price below threshold, preparing stake of {format_balance(target_amount)}"
            )

            if coldkey_balance is None:
                bt.logging.warning("Coldkey balance unavailable; skipping this interval")
                time.sleep(args.interval)
                continue

            available_tao = coldkey_balance.tao
            requested_tao = args.amount_tao

            if available_tao <= 0:
                bt.logging.warning(
                    f"No liquid TAO available in coldkey balance (available {format_balance(coldkey_balance)})"
                )
                time.sleep(args.interval)
                continue

            if not args.allow_partial and available_tao < requested_tao:
                bt.logging.warning(
                    f"Insufficient coldkey balance (have {available_tao:.9f} TAO, "
                    f"need {requested_tao:.9f} TAO). Enable --allow-partial to stake the available amount."
                )
                time.sleep(args.interval)
                continue

            stake_tao = min(available_tao, requested_tao) if args.allow_partial else requested_tao

            if stake_tao <= 0:
                bt.logging.warning("Calculated stake amount is zero; skipping this interval")
                time.sleep(args.interval)
                continue

            amount_to_stake = Balance.from_tao(stake_tao, netuid=args.netuid)

            if args.dry_run:
                bt.logging.info(
                    f"Dry run: would stake {format_balance(amount_to_stake)} to netuid {args.netuid}"
                )
                stakes_completed += 1
            else:
                bt.logging.info(
                    f"Submitting stake of {format_balance(amount_to_stake)} to netuid {args.netuid}"
                )
                success = False
                try:
                    success = subtensor.add_stake(
                        wallet=wallet,
                        hotkey_ss58=hotkey_ss58,
                        netuid=args.netuid,
                        amount=amount_to_stake,
                        wait_for_inclusion=args.wait_for_inclusion,
                        wait_for_finalization=args.wait_for_finalization,
                        safe_staking=args.safe_staking,
                        allow_partial_stake=args.allow_partial,
                        rate_tolerance=args.rate_tolerance,
                    )
                except Exception as err:  # pylint: disable=broad-except
                    bt.logging.error(f"add_stake submission failed: {err}")
                else:
                    if success:
                        bt.logging.success("add_stake extrinsic submitted successfully")
                        stakes_completed += 1
                    else:
                        bt.logging.warning("add_stake extrinsic was not confirmed as successful")

            if args.max_stakes and stakes_completed >= args.max_stakes:
                break

        time.sleep(args.interval)

    bt.logging.info(f"Finished after executing {stakes_completed} stake(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        bt.logging.warning("Auto-buy watcher interrupted by user")
        raise SystemExit(130)