# SAVANNAH — Solana Wallet & Token Ecosystem Plan

## Overview

Build a production-grade Solana wallet and token ecosystem into Think Box AI. The wallet (codename **Savannah**) combines meme coin fun with real utility: AI-powered trading research, NFT hybridization via MPL-404, and multi-agent coordination for DeFi operations.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (public/)                                         │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ Wallet  │ │ Token    │ │ NFT     │ │ AI Trading      │  │
│  │ UI      │ │ Launch   │ │ Market  │ │ Terminal        │  │
│  └─────────┘ └──────────┘ └─────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Backend (backend/)                                         │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐  │
│  │ Solana API  │ │ WebSocket    │ │ Agent Orchestration  │  │
│  │ Proxy       │ │ Event Feed   │ │ Engine               │  │
│  └─────────────┘ └──────────────┘ └──────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Core (core/)                                               │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ solana/  │ │ multi_    │ │ observ-  │ │ cost_        │  │
│  │ wallet   │ │ agent     │ │ ability  │ │ tracker      │  │
│  └──────────┘ └───────────┘ └──────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Smart Contracts (anchor/)                                  │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ THNK     │ │ SPL Token │ │ MPL-404  │ │ Staking      │  │
│  │ Token    │ │ Factory   │ │ Hybrid   │ │ Vault        │  │
│  └──────────┘ └───────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Savannah Wallet (Core)

### 1.1 Wallet Infrastructure
- **Key generation**: Ed25519 keypair via `@solana/web3.js` or Rust
- **Key encryption**: AES-256-GCM encrypted keypair storage (password-derived)
- **HD wallet**: BIP-44 mnemonic support (12/24 word seed)
- **Multi-wallet**: Support for Phantom, Solflare, Backpack via wallet-adapter
- **Network**: Mainnet, Devnet, Localnet (via Surfpool)

### 1.2 Wallet CLI (`thinkbox wallet`)
- `wallet create` — Generate new keypair with mnemonic backup
- `wallet import` — Import from mnemonic or private key
- `wallet balance` — Check SOL and SPL token balances
- `wallet send` — Send SOL or SPL tokens
- `wallet history` — Transaction history
- `wallet sign` — Sign arbitrary messages
- `wallet export` — Export public key / encrypted backup

### 1.3 Wallet UI (Frontend)
- Connect wallet (Phantom, Solflare, Backpack via wallet-adapter)
- View SOL balance, SPL tokens, NFTs
- Send/receive interface
- Transaction history with Solscan links
- Dark theme matching existing design

---

## Phase 2: Token Launchpad

### 2.1 SPL Token Factory
- Create fungible tokens with metadata (name, symbol, image, URI)
- Configurable decimals (standard: 9)
- Initial mint supply
- Token Extensions support (transfer fees, confidential transfers, metadata pointer)
- Metaplex Token Metadata integration for on-chain metadata

### 2.2 Meme Coin Features
- **Bonding curve launch**: Price increases as supply grows (Pump.fun style)
- **Fair launch**: No presale, everyone buys at market price
- **Liquidity pool**: Auto-create Raydium/Orca pool on graduation
- **Anti-rug**: Locked liquidity, renounced mint authority option
- **Viral mechanics**: Referral rewards, creator fees (1% of trades)

### 2.3 Token CLI (`thinkbox token`)
- `token create` — Launch new SPL token
- `token mint` — Mint additional supply
- `token burn` — Burn tokens
- `token freeze` — Freeze token account
- `token metadata` — Update token metadata
- `token airdrop` — Airdrop to multiple wallets

### 2.4 Token UI
- Token creation wizard (name, symbol, image, supply, description)
- Real-time bonding curve visualization
- Trading interface (buy/sell via Jupiter aggregator)
- Token analytics (holders, volume, market cap)

---

## Phase 3: MPL-404 Hybrid NFTs

### 3.1 Hybrid DeFi System
- Create collections that exist as both fungible tokens AND NFTs
- Hold 1,000,000 fungible tokens = redeem 1 NFT with random traits
- Burn NFT to recover fungible tokens
- Trait rarity system with on-chain metadata

### 3.2 NFT Infrastructure
- **Metaplex Core**: Single-account design, 80% cheaper minting
- **Bubblegum V2**: Compressed NFTs for mass airdrops (0.00001 SOL per cNFT)
- **Royalty enforcement**: Creator earnings on every trade
- **Plugin system**: Staking, attributes, delegates

### 3.3 NFT CLI (`thinkbox nft`)
- `nft mint` — Mint single NFT
- `nft collection` — Create NFT collection
- `nft airdrop` — Compressed NFT airdrop to thousands
- `nft trade` — Buy/sell on marketplace
- `nft hybrid` — Create MPL-404 hybrid collection

### 3.4 NFT UI
- Collection browser with trait filtering
- Mint interface (upload image, set metadata, mint)
- Trait swapping (fungible ↔ NFT conversion)
- Marketplace with Jupiter-powered trades

---

## Phase 4: AI Trading Agents

### 4.1 Trading Research Agent
- **On-chain analysis**: Holder distribution, whale tracking, liquidity health
- **Social sentiment**: Twitter/Discord mention tracking
- **Risk scoring**: Rug pull detection, contract audit verification
- **Price prediction**: Technical analysis on DEX trading data

### 4.2 Multi-Agent Trading System
- **Sniper agent**: First-block buying on new launches (when GPU available)
- **Monitor agent**: Track portfolio positions and alert on changes
- **Research agent**: Continuous due diligence on held tokens
- **Execution agent**: Automated trading with configurable strategies

### 4.3 Trading CLI (`thinkbox trade`)
- `trade quote` — Get Jupiter price quote
- `trade swap` — Execute token swap via Jupiter
- `trade limit` — Set limit orders
- `trade history` — View trading P&L
- `trade agents` — Manage trading agents

### 4.4 Trading UI
- Real-time price charts (Dexscreener/GeckoTerminal embeds)
- Jupiter swap interface
- Agent dashboard (active agents, positions, P&L)
- Risk alerts and notifications

---

## Phase 5: Smart Contracts (Anchor)

### 5.1 THNK Token Program
```rust
#[program]
pub mod thnk_token {
    pub fn initialize(ctx: Context<Initialize>, params: TokenParams) -> Result<()>
    pub fn mint(ctx: Context<Mint>, amount: u64) -> Result<()>
    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()>
    pub fn unstake(ctx: Context<Unstake>, amount: u64) -> Result<()>
    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()>
}
```

### 5.2 Staking Vault
- Time-locked staking with APY rewards
- NFT boost: Hold specific NFT for staking multiplier
- Governance: Staked tokens grant voting power

### 5.3 Bonding Curve Program
- Configurable curve (linear, exponential, sigmoid)
- Graduation mechanism: Auto-create DEX pool at target market cap
- Creator fees: Configurable percentage to creator wallet

### 5.4 MPL-404 Hybrid Program
- Swap program for fungible ↔ NFT conversion
- Random trait assignment on NFT mint
- Trait rarity configuration
- Liquidity pool integration

---

## Phase 6: Integration with Think Box AI

### 6.1 Update Existing Modules
- `think_box_ai/token.py` → Solana token interface (SPL + metadata)
- `core/tools/` → Add solana_wallet, solana_token, solana_nft, solana_trade tools
- `core/observability.py` → Trace Solana transactions as spans
- `core/cost_tracker.py` → Track SOL spent on transactions
- `core/multi_agent.py` → Multi-agent for trading, research, validation
- `core/evaluation.py` → Evaluate trading strategies
- `backend/main.py` → Add Solana API endpoints

### 6.2 New CLI Commands (20+ new)
```
thinkbox wallet    — Key management, balances, transfers
thinkbox token     — SPL token creation, minting, airdrops
thinkbox nft       — NFT minting, collections, marketplace
thinkbox trade     — Jupiter swaps, limit orders, agents
thinkbox stake     — Staking, rewards, governance
thinkbox hybrid    — MPL-404 hybrid creation and swapping
thinkbox scan      — Wallet/token analysis and risk scoring
thinkbox agents    — AI trading agent management
```

### 6.3 New Frontend Pages (8+ new)
```
/wallet/           — Wallet dashboard
/tokens/           — Token launchpad
/nfts/             — NFT marketplace
/trade/            — Trading terminal
/stake/            — Staking interface
/hybrid/           — MPL-404 hybrid interface
/agents/           — AI agent dashboard
/analytics/        — On-chain analytics
```

### 6.4 Backend API Endpoints
```
POST /api/v1/wallet/create
GET  /api/v1/wallet/:address/balance
POST /api/v1/wallet/send
POST /api/v1/token/create
POST /api/v1/token/mint
POST /api/v1/nft/mint
POST /api/v1/trade/swap
GET  /api/v1/trade/quote
POST /api/v1/stake
GET  /api/v1/agents
WS   /ws/wallet/:address
```

---

## Phase 7: Development Tooling

### 7.1 Solana CLI Integration
- Install Solana CLI (Agave) in Docker image
- Anchor framework for smart contract development
- Surfpool for local testing (replaces solana-test-validator)
- @solana/kit for TypeScript client development

### 7.2 AI Development Guidance
- Integrate `solana-dev-skill` patterns into agent prompts
- Security best practices: account validation, rent exemption, compute budget
- Common error handling: insufficient funds, account not found, CPI failures

### 7.3 Testing Infrastructure
- Unit tests with LiteSVM (fast, in-process Solana VM)
- Integration tests with Surfpool (mainnet fork)
- Anchor test framework for program tests

---

## Implementation Priority

| Phase | Feature | Impact | Effort |
|-------|---------|--------|--------|
| 1 | Savannah Wallet | High | Medium |
| 2 | Token Launchpad | High | Medium |
| 3 | MPL-404 NFTs | Very High | High |
| 4 | AI Trading Agents | Very High | High |
| 5 | Smart Contracts | Core | Very High |
| 6 | Integration | Core | Medium |
| 7 | Dev Tooling | Enabler | Medium |

**Recommended order**: 1 → 6 → 2 → 3 → 4 → 5 → 7

---

## Key Dependencies

```toml
# JavaScript/TypeScript
@solana/web3.js = "^2.0"
@solana/kit = "^6.0"
@metaplex-foundation/mpl-core = "^2.0"
@metaplex-foundation/mpl-token-metadata = "^4.0"
@metaplex-foundation/mpl-bubblegum = "^5.0"
@metaplex-foundation/mpl-hybrid = "^1.0"
@jup-ag/api = "^6.0"  # Jupiter aggregator
@solana/wallet-adapter = "^1.0"

# Rust (Anchor programs)
anchor-lang = "1.0"
mpl-core = "2.0"
mpl-token-metadata = "4.0"
```

---

## Security Considerations

- **Key management**: Never store private keys in plaintext. AES-256-GCM with user password.
- **Transaction simulation**: Simulate all transactions before signing (via `simulateTransaction`)
- **Rate limiting**: Prevent abuse of token creation and trading endpoints
- **Approval gates**: Human approval for transactions above configurable thresholds
- **Audit**: Smart contract audit before mainnet deployment
- **Insider controls**: Renounce mint authority, lock liquidity, timelock team tokens
