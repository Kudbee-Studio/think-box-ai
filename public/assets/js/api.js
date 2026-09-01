/**
 * Think Box AI — Data Layer
 * Fetches live data from Doginals APIs and caches results
 */

const API = {
  // Doginals content CDN
  CDN: "https://cdn.doggy.market/content",
  // Doggy.market API endpoints (public)
  MARKET: "https://api.doggy.market",
  // Fallback to local data
  LOCAL: "/data",

  // Cache
  _cache: {},
  _ttl: 60000, // 1 minute

  async fetch(url, opts = {}) {
    const key = url + JSON.stringify(opts);
    if (this._cache[key] && Date.now() - this._cache[key].ts < this._ttl) {
      return this._cache[key].data;
    }
    try {
      const res = await fetch(url, { ...opts, signal: AbortSignal.timeout(5000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      this._cache[key] = { data, ts: Date.now() };
      return data;
    } catch (e) {
      console.warn(`API fetch failed: ${url}`, e);
      return null;
    }
  },

  // Get inscription content URL
  inscriptionUrl(id) {
    return `${this.CDN}/${id}`;
  },

  // Get collection data
  async getCollection(slug) {
    return this.fetch(`${this.MARKET}/collections/${slug}`);
  },

  // Get all collections
  async getCollections() {
    return this.fetch(`${this.MARKET}/collections`);
  },

  // Get DRC-20 tokens
  async getTokens() {
    return this.fetch(`${this.MARKET}/tokens`);
  },

  // Get token by ticker
  async getToken(ticker) {
    return this.fetch(`${this.MARKET}/token/${ticker}`);
  },

  // Get recent sales
  async getActivity() {
    return this.fetch(`${this.MARKET}/activity`);
  },

  // Get inscription details
  async getInscription(id) {
    return this.fetch(`${this.MARKET}/inscription/${id}`);
  },
};

// Local fallback data (for demo/offline)
const LOCAL_DATA = {
  collections: [
    {
      slug: "doginaldogs",
      name: "Doginal Dogs",
      supply: 10000,
      floor: 350,
      floorUsd: 25.13,
      volume24h: 1871,
      listed: 1218,
      owners: 10000,
      description: "10,000 Distinctive Pixel Dogs inscribed on the Doge Blockchain",
      inscriptionIcon: "doginaldogs.png",
    },
    {
      slug: "minidoges",
      name: "Doginal Mini Doges",
      supply: 10000,
      floor: 390,
      floorUsd: 27.96,
      volume24h: 1871,
      listed: 1218,
      owners: 10000,
      description: "Much Wow! Very early! Starting shibescription 14578!",
      inscriptionIcon: "minidoges.png",
    },
    {
      slug: "dogemaps",
      name: "Doge Maps",
      supply: 10000,
      floor: 13.9,
      floorUsd: 0.99,
      volume24h: 523,
      listed: 890,
      owners: 5420,
      description: "Doge's version of Bitmap. Virtual real estate on-chain.",
      inscriptionIcon: "dogemaps.png",
    },
    {
      slug: "dogebuds",
      name: "DogeBuds",
      supply: 5000,
      floor: 26,
      floorUsd: 1.86,
      volume24h: 312,
      listed: 445,
      owners: 3200,
      description: "5,000 unique buds inscribed on Dogecoin.",
      inscriptionIcon: "dogebuds.png",
    },
    {
      slug: "dogerunestone",
      name: "Doge Runestone",
      supply: 21000000,
      floor: 19,
      floorUsd: 1.36,
      volume24h: 890,
      listed: 2100,
      owners: 15000,
      description: "The first Runestone on Dogecoin. 21M supply.",
      inscriptionIcon: "runestone.png",
    },
    {
      slug: "dcex",
      name: "DCEx",
      supply: 8000,
      floor: 45,
      floorUsd: 3.21,
      volume24h: 215,
      listed: 567,
      owners: 4100,
      description: "Doginal Community Exchange tokens.",
      inscriptionIcon: "dcex.png",
    },
  ],
  tokens: [
    { ticker: "dogi", name: "DOGI", price: 0.097, change24h: 4.6, volume24h: 1957, marketCap: 8220571, holders: 11090 },
    { ticker: "dbit", name: "DBIT", price: 0.065, change24h: -2.1, volume24h: 890, marketCap: 2005154, holders: 2790 },
    { ticker: "dhub", name: "DHUB", price: 0.0014, change24h: 0, volume24h: 0, marketCap: 1601034, holders: 3048 },
    { ticker: "xton", name: "XTON", price: 8, change24h: 1.2, volume24h: 450, marketCap: 1200000, holders: 1200 },
    { ticker: "dwag", name: "DWAG", price: 0.002, change24h: -5.3, volume24h: 120, marketCap: 450000, holders: 890 },
    { ticker: "dpex", name: "DPEX", price: 0.015, change24h: 12.4, volume24h: 2100, marketCap: 890000, holders: 1560 },
  ],
  activity: [
    { type: "sale", collection: "minidoges", inscription: "Doginal Mini Doges #8100", price: 390, time: "2m ago", buyer: "D8vF...kP9n" },
    { type: "sale", collection: "doginaldogs", inscription: "Doginal Dog #3446", price: 450, time: "5m ago", buyer: "DSV1...DPn" },
    { type: "list", collection: "minidoges", inscription: "Doginal Mini Doges #7532", price: 399, time: "8m ago" },
    { type: "sale", collection: "dogemaps", inscription: "DogeMap #1247", price: 13.9, time: "12m ago", buyer: "D7xR...mL2q" },
    { type: "list", collection: "dogebuds", inscription: "DogeBud #892", price: 26, time: "15m ago" },
    { type: "sale", collection: "dcex", inscription: "DCEx #2341", price: 45, time: "22m ago", buyer: "DAa3...nP7k" },
    { type: "transfer", collection: "doginaldogs", inscription: "Doginal Dog #1203", price: 0, time: "28m ago" },
    { type: "sale", collection: "runestone", inscription: "Doge Runestone #5421", price: 19, time: "35m ago", buyer: "D5mK...jR8s" },
  ],
};
