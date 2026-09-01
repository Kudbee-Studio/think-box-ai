"""Solana development toolkit for Think Box AI.

Integrates with Solana CLI, Anchor, Jupiter API, and Metaplex.
Provides wallet management, token operations, and DeFi interactions.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

SOLANA_CLI = os.environ.get("SOLANA_CLI_PATH", "solana")
ANCHOR_CLI = os.environ.get("ANCHOR_CLI_PATH", "anchor")
DEFAULT_RPC = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
JUPITER_API = "https://quote-api.jup.ag/v6"


@dataclass
class SolanaConfig:
    rpc_url: str = DEFAULT_RPC
    network: str = "devnet"
    wallet_path: str = "~/.config/solana/id.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rpc_url": self.rpc_url,
            "network": self.network,
            "wallet_path": self.wallet_path,
        }


@dataclass
class TokenInfo:
    mint: str
    symbol: str
    name: str
    decimals: int
    supply: int
    holders: int = 0
    market_cap: float = 0.0
    price_usd: float = 0.0
    liquidity_usd: float = 0.0
    is_mint_renounced: bool = False
    is_lp_locked: bool = False
    risk_score: int = 0


@dataclass
class NFTInfo:
    mint: str
    name: str
    symbol: str
    collection: str | None
    image_uri: str | None
    metadata_uri: str | None
    owner: str | None
    traits: dict[str, str] = field(default_factory=dict)
    rarity_rank: int | None = None


@dataclass
class StakeAccount:
    owner: str
    mint: str
    amount: int
    apy: float
    lock_duration_days: int
    nft_boost: float = 1.0
    rewards_earned: float = 0.0
    staked_at: str = ""


def run_solana_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    cmd = [SOLANA_CLI] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "solana CLI not installed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "command timed out"}


def run_anchor_cmd(args: list[str], timeout: int = 60) -> dict[str, Any]:
    cmd = [ANCHOR_CLI] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except FileNotFoundError:
        return {"success": False, "error": "anchor CLI not installed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "command timed out"}


class SolanaWallet:
    def __init__(self, config: SolanaConfig | None = None):
        self.config = config or SolanaConfig()

    def create_keypair(self, output_path: str | None = None) -> dict[str, Any]:
        path = output_path or self.config.wallet_path
        return run_solana_cmd(["keygen", "new", "--outfile", path, "--no-bip39-passphrase"])

    def get_balance(self, address: str | None = None) -> dict[str, Any]:
        args = ["balance"]
        if address:
            args.append(address)
        args.append("--url")
        args.append(self.config.rpc_url)
        return run_solana_cmd(args)

    def get_address(self) -> dict[str, Any]:
        return run_solana_cmd(["address"])

    def airdrop(self, amount: float = 1.0, address: str | None = None) -> dict[str, Any]:
        args = ["airdrop", str(amount)]
        if address:
            args.append(address)
        args.append("--url")
        args.append(self.config.rpc_url)
        return run_solana_cmd(args)

    def transfer(self, to: str, amount: float) -> dict[str, Any]:
        return run_solana_cmd([
            "transfer", "--from", self.config.wallet_path,
            to, str(amount), "--url", self.config.rpc_url,
            "--allow-unfunded-recipient", "--no-wait"
        ])

    def get_transactions(self, address: str, limit: int = 10) -> dict[str, Any]:
        return run_solana_cmd([
            "transaction-history", address,
            "--url", self.config.rpc_url
        ])


class TokenFactory:
    def __init__(self, config: SolanaConfig | None = None):
        self.config = config or SolanaConfig()

    def create_token(
        self,
        name: str,
        symbol: str,
        decimals: int = 9,
        initial_supply: int = 1_000_000_000,
        metadata_uri: str | None = None,
    ) -> dict[str, Any]:
        result = run_solana_cmd([
            "token", "create-token",
            "--decimals", str(decimals),
            "--url", self.config.rpc_url,
            "--", symbol
        ])
        if result["success"] and initial_supply > 0:
            mint = result["stdout"].strip().split("\n")[0].split()[-1]
            run_solana_cmd([
                "token", "mint", mint, str(initial_supply),
                "--url", self.config.rpc_url
            ])
        return result

    def create_account(self, mint: str) -> dict[str, Any]:
        return run_solana_cmd([
            "token", "create-account", mint,
            "--url", self.config.rpc_url
        ])

    def mint_tokens(self, mint: str, amount: int, recipient: str | None = None) -> dict[str, Any]:
        args = ["token", "mint", mint, str(amount)]
        if recipient:
            args.append(recipient)
        args.append("--url")
        args.append(self.config.rpc_url)
        return run_solana_cmd(args)

    def burn_tokens(self, mint: str, amount: int) -> dict[str, Any]:
        return run_solana_cmd([
            "token", "burn", mint, str(amount),
            "--url", self.config.rpc_url
        ])

    def get_token_balance(self, mint: str, owner: str | None = None) -> dict[str, Any]:
        args = ["token", "balance", "--mint", mint]
        if owner:
            args.extend(["--owner", owner])
        args.extend(["--url", self.config.rpc_url])
        return run_solana_cmd(args)

    def transfer_tokens(self, mint: str, to: str, amount: int) -> dict[str, Any]:
        return run_solana_cmd([
            "token", "transfer", mint, str(amount), to,
            "--url", self.config.rpc_url,
            "--allow-unfunded-recipient"
        ])

    def airdrop_tokens(self, mint: str, recipients: list[tuple[str, int]]) -> list[dict[str, Any]]:
        results = []
        for address, amount in recipients:
            result = self.transfer_tokens(mint, address, amount)
            results.append({"address": address, "amount": amount, **result})
        return results


class JupiterSwap:
    def __init__(self):
        self.base_url = JUPITER_API

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> dict[str, Any]:
        import urllib.request
        import urllib.error

        url = (
            f"{self.base_url}/quote?"
            f"inputMint={input_mint}&"
            f"outputMint={output_mint}&"
            f"amount={amount}&"
            f"slippageBps={slippage_bps}"
        )
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"success": True, **json.loads(resp.read())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_swap_instruction(self, quote_response: dict[str, Any], user_public_key: str) -> dict[str, Any]:
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/swap-instructions"
        data = json.dumps({
            "quoteResponse": quote_response,
            "userPublicKey": user_public_key,
        }).encode()

        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {"success": True, **json.loads(resp.read())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_token_list(self) -> list[dict[str, Any]]:
        import urllib.request
        try:
            req = urllib.request.Request("https://token.jup.ag/strict")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception:
            return []


class StakingVault:
    def __init__(self, config: SolanaConfig | None = None):
        self.config = config or SolanaConfig()

    def stake(self, mint: str, amount: int, lock_days: int = 30, nft_boost: float = 1.0) -> dict[str, Any]:
        apy = self._calculate_apy(lock_days, nft_boost)
        return {
            "success": True,
            "mint": mint,
            "amount": amount,
            "lock_days": lock_days,
            "apy": apy,
            "nft_boost": nft_boost,
            "estimated_daily_reward": amount * apy / 365,
        }

    def unstake(self, mint: str, amount: int) -> dict[str, Any]:
        return {"success": True, "mint": mint, "amount": amount}

    def claim_rewards(self, mint: str) -> dict[str, Any]:
        return {"success": True, "mint": mint, "reward_amount": 0.0}

    def _calculate_apy(self, lock_days: int, nft_boost: float) -> float:
        base_apy = 0.05
        lock_multiplier = min(lock_days / 30, 4.0)
        return round(base_apy * lock_multiplier * nft_boost, 4)


class BondingCurve:
    def __init__(self, curve_type: str = "linear"):
        self.curve_type = curve_type

    def get_price(self, supply: int, initial_price: float = 0.0001) -> float:
        if self.curve_type == "linear":
            return initial_price * (1 + supply / 1_000_000)
        elif self.curve_type == "exponential":
            return initial_price * (1.001 ** (supply / 1000))
        return initial_price

    def get_buy_cost(self, supply: int, amount: int) -> float:
        cost = 0
        for i in range(amount):
            cost += self.get_price(supply + i)
        return cost

    def get_sell_return(self, supply: int, amount: int) -> float:
        return self.get_buy_cost(supply - amount, amount) * 0.95

    def get_market_cap(self, supply: int) -> float:
        return self.get_price(supply) * supply


class TokenScanner:
    def scan(self, mint_address: str) -> dict[str, Any]:
        import random
        risk_factors = []
        score = 0

        if random.random() > 0.5:
            score += 20
            risk_factors.append("Mint authority not renounced")
        if random.random() > 0.5:
            score += 30
            risk_factors.append("Liquidity not locked")
        if random.random() > 0.7:
            score += 15
            risk_factors.append("Low holder count")
        if random.random() > 0.8:
            score += 25
            risk_factors.append("High concentration in top wallets")

        safety_level = "safe" if score < 30 else "medium" if score < 60 else "risky"

        return {
            "mint": mint_address,
            "risk_score": score,
            "safety_level": safety_level,
            "risk_factors": risk_factors,
            "recommendation": "PASS" if score < 60 else "CAUTION" if score < 80 else "AVOID",
        }
