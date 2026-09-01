"""Solana CLI commands for Think Box AI."""

from __future__ import annotations

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


def handle_wallet_command(args) -> None:
    from core.solana import SolanaWallet, SolanaConfig

    config = SolanaConfig(network=args.network or "devnet")
    wallet = SolanaWallet(config)
    sub = args.wallet_command

    if sub == "create":
        result = wallet.create_keypair(args.output)
        if is_json_mode():
            output_json(result)
            return
        if result.get("success"):
            print(green("  Keypair created successfully"))
            print(f"  Path: {args.output or config.wallet_path}")
        else:
            print(yellow(f"  Error: {result.get('error', 'unknown')}"))

    elif sub == "balance":
        result = wallet.get_balance(args.address)
        if is_json_mode():
            output_json(result)
            return
        if result.get("success"):
            print(bold(f"\n  Balance: {result.get('stdout', '0').strip()}"))
        else:
            print(yellow(f"  Error: {result.get('error', 'unknown')}"))

    elif sub == "airdrop":
        result = wallet.airdrop(args.amount or 1.0, args.address)
        if is_json_mode():
            output_json(result)
            return
        if result.get("success"):
            print(green(f"  Airdropped {args.amount or 1.0} SOL"))
        else:
            print(yellow(f"  Error: {result.get('error', 'unknown')}"))

    elif sub == "transfer":
        result = wallet.transfer(args.to, args.amount)
        if is_json_mode():
            output_json(result)
            return
        if result.get("success"):
            print(green(f"  Transferred {args.amount} SOL to {args.to[:12]}..."))
        else:
            print(yellow(f"  Error: {result.get('error', 'unknown')}"))

    elif sub == "address":
        result = wallet.get_address()
        if is_json_mode():
            output_json(result)
            return
        print(f"  {result.get('stdout', 'N/A').strip()}")
    else:
        print("Usage: thinkbox wallet {create|balance|airdrop|transfer|address}")


def handle_swap_command(args) -> None:
    from core.solana import JupiterSwap

    swap = JupiterSwap()
    sub = args.swap_command

    if sub == "quote":
        result = swap.get_quote(args.input_mint, args.output_mint, args.amount, args.slippage or 50)
        if is_json_mode():
            output_json(result)
            return
        if result.get("success"):
            print(bold(f"\n  Quote: {args.amount} → {result.get('outAmount', 'N/A')}"))
            print(f"  Price impact: {result.get('priceImpactPct', 'N/A')}%")
        else:
            print(yellow(f"  Error: {result.get('error', 'unknown')}"))

    elif sub == "tokens":
        tokens = swap.get_token_list()
        if is_json_mode():
            output_json(tokens[:20])
            return
        print(bold(f"\n  Available Tokens ({len(tokens)}):"))
        for t in tokens[:20]:
            print(f"    {t.get('symbol', 'N/A'):10} {t.get('address', '')[:20]}...")
    else:
        print("Usage: thinkbox swap {quote|tokens}")


def handle_stake_command(args) -> None:
    from core.solana import StakingVault

    vault = StakingVault()
    sub = args.stake_command

    if sub == "deposit":
        result = vault.stake(args.mint, args.amount, args.lock_days or 30, args.nft_boost or 1.0)
        if is_json_mode():
            output_json(result)
            return
        print(green(f"  Staked {args.amount} tokens"))
        print(f"  APY: {result.get('apy', 0) * 100:.2f}%")
        print(f"  Daily reward: ~{result.get('estimated_daily_reward', 0):.6f}")

    elif sub == "unstake":
        result = vault.unstake(args.mint, args.amount)
        if is_json_mode():
            output_json(result)
            return
        print(green(f"  Unstaked {args.amount} tokens"))

    elif sub == "rewards":
        result = vault.claim_rewards(args.mint)
        if is_json_mode():
            output_json(result)
            return
        print(f"  Rewards: {result.get('reward_amount', 0)}")
    else:
        print("Usage: thinkbox stake {deposit|unstake|rewards}")


def handle_scan_command(args) -> None:
    from core.solana import TokenScanner

    scanner = TokenScanner()
    result = scanner.scan(args.mint)
    if is_json_mode():
        output_json(result)
        return

    print(bold(f"\n  Token Scan: {args.mint[:12]}..."))
    print(dim("  " + "─" * 40))
    print(f"  Risk Score: {result['risk_score']}/100")
    print(f"  Safety: {result['safety_level'].upper()}")
    print(f"  Verdict: {result['recommendation']}")
    if result.get("risk_factors"):
        print(f"\n  {bold('Risk Factors:')}")
        for f in result["risk_factors"]:
            print(f"    {yellow('⚠')} {f}")


def handle_bonding_command(args) -> None:
    from core.solana import BondingCurve

    curve = BondingCurve(args.curve_type or "linear")
    sub = args.bonding_command

    if sub == "price":
        price = curve.get_price(args.supply)
        if is_json_mode():
            output_json({"supply": args.supply, "price": price})
            return
        print(f"  Price at supply {args.supply}: {price:.8f} SOL")

    elif sub == "cost":
        cost = curve.get_buy_cost(args.supply, args.amount)
        if is_json_mode():
            output_json({"cost": cost})
            return
        print(f"  Cost to buy {args.amount}: {cost:.4f} SOL")

    elif sub == "market-cap":
        mc = curve.get_market_cap(args.supply)
        if is_json_mode():
            output_json({"market_cap": mc})
            return
        print(f"  Market cap: {mc:.2f} SOL")
    else:
        print("Usage: thinkbox bonding {price|cost|market-cap}")
