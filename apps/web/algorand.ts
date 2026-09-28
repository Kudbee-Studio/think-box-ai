// Read-only Algorand access through public AlgoNode endpoints (no API key, no SDK, no wallet).
// Everything here only reads chain state; signing and sending transactions are deliberately absent.

export type AlgorandNetwork = 'testnet' | 'mainnet';
export const ALGORAND_ACTIONS = ['status', 'account', 'asset', 'application', 'transaction', 'account_transactions'] as const;
export type AlgorandAction = (typeof ALGORAND_ACTIONS)[number];

export interface AlgorandEndpoints {
  algod: Record<AlgorandNetwork, string>;
  indexer: Record<AlgorandNetwork, string>;
}

export const PUBLIC_ENDPOINTS: AlgorandEndpoints = {
  algod: { testnet: 'https://testnet-api.algonode.cloud', mainnet: 'https://mainnet-api.algonode.cloud' },
  indexer: { testnet: 'https://testnet-idx.algonode.cloud', mainnet: 'https://mainnet-idx.algonode.cloud' },
};

const ADDRESS = /^[A-Z2-7]{58}$/;
const TXID = /^[A-Z2-7]{52}$/;
const MICRO = 1_000_000;

const usesIndexer = (action: AlgorandAction) => action === 'transaction' || action === 'account_transactions';

export function algorandHost(action: AlgorandAction, network: AlgorandNetwork, endpoints = PUBLIC_ENDPOINTS): string {
  return new URL(usesIndexer(action) ? endpoints.indexer[network] : endpoints.algod[network]).hostname;
}

function printable(bytes: Buffer): string | null {
  const text = bytes.toString('utf8');
  return /^[\x20-\x7e]*$/.test(text) ? text : null;
}

/** Decodes TEAL global/local state (base64 keys, typed values) into readable key/value pairs. */
export function decodeState(state: Array<{ key: string; value: { type: number; bytes?: string; uint?: number } }> = []): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  for (const entry of state) {
    const keyBytes = Buffer.from(entry.key, 'base64');
    const key = printable(keyBytes) ?? `0x${keyBytes.toString('hex')}`;
    if (entry.value.type === 2) out[key] = entry.value.uint ?? 0;
    else {
      const valueBytes = Buffer.from(entry.value.bytes ?? '', 'base64');
      out[key] = printable(valueBytes) ?? `base64:${entry.value.bytes ?? ''}`;
    }
  }
  return out;
}

async function getJson(url: string, signal?: AbortSignal): Promise<any> {
  const response = await fetch(url, { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000) });
  const body = (await response.json().catch(() => ({}))) as { message?: string };
  if (response.status === 404) throw new Error(`Not found on Algorand: ${body.message ?? url}`);
  if (!response.ok) throw new Error(`Algorand API HTTP ${response.status}: ${body.message ?? ''}`.trim());
  return body;
}

function need(value: unknown, pattern: RegExp | 'id', label: string): string {
  const text = String(value ?? '').trim();
  if (pattern === 'id') {
    if (!/^\d{1,20}$/.test(text)) throw new Error(`${label} must be a numeric id`);
  } else if (!pattern.test(text)) {
    throw new Error(`${label} is not a valid Algorand ${label}`);
  }
  return text;
}

export function parseNetwork(value: unknown): AlgorandNetwork {
  const network = String(value ?? 'testnet').toLowerCase();
  if (network !== 'testnet' && network !== 'mainnet') throw new Error('network must be testnet or mainnet');
  return network;
}

export function parseAction(value: unknown): AlgorandAction {
  const action = String(value ?? '');
  if (!(ALGORAND_ACTIONS as readonly string[]).includes(action)) throw new Error(`action must be one of: ${ALGORAND_ACTIONS.join(', ')}`);
  return action as AlgorandAction;
}

/** Throws on input that can never succeed, so callers can reject it before any approval prompt or request. */
export function validateAlgorandInput(input: { action: unknown; network?: unknown; address?: unknown; id?: unknown; txid?: unknown }): void {
  const action = parseAction(input.action);
  parseNetwork(input.network);
  if (action === 'account' || action === 'account_transactions') need(input.address, ADDRESS, 'address');
  if (action === 'asset') need(input.id, 'id', 'asset id');
  if (action === 'application') need(input.id, 'id', 'application id');
  if (action === 'transaction') need(input.txid, TXID, 'transaction id');
}

export async function algorandQuery(
  input: { action: unknown; network?: unknown; address?: unknown; id?: unknown; txid?: unknown; limit?: unknown },
  options: { endpoints?: AlgorandEndpoints; signal?: AbortSignal } = {},
): Promise<Record<string, unknown>> {
  validateAlgorandInput(input);
  const endpoints = options.endpoints ?? PUBLIC_ENDPOINTS;
  const action = parseAction(input.action);
  const network = parseNetwork(input.network);
  const algod = endpoints.algod[network];
  const indexer = endpoints.indexer[network];

  switch (action) {
    case 'status': {
      const s = await getJson(`${algod}/v2/status`, options.signal);
      return { network, last_round: s['last-round'], seconds_since_last_round: Math.round((s['time-since-last-round'] ?? 0) / 1e9), catching_up: (s['catchup-time'] ?? 0) > 0, last_version: s['last-version'] };
    }
    case 'account': {
      const address = need(input.address, ADDRESS, 'address');
      const a = await getJson(`${algod}/v2/accounts/${address}?exclude=created-apps,created-assets`, options.signal);
      const assets = (a.assets ?? []) as Array<{ 'asset-id': number; amount: number; 'is-frozen': boolean }>;
      return {
        network,
        address,
        balance_algo: (a.amount ?? 0) / MICRO,
        min_balance_algo: (a['min-balance'] ?? 0) / MICRO,
        status: a.status,
        assets_held: a['total-assets-opted-in'] ?? assets.length,
        apps_opted_in: a['total-apps-opted-in'] ?? 0,
        apps_created: a['total-created-apps'] ?? 0,
        assets_created: a['total-created-assets'] ?? 0,
        holdings: assets.slice(0, 20).map((h) => ({ asset_id: h['asset-id'], amount_base_units: h.amount, frozen: h['is-frozen'] })),
      };
    }
    case 'asset': {
      const id = need(input.id, 'id', 'asset id');
      const { params: p } = await getJson(`${algod}/v2/assets/${id}`, options.signal);
      return {
        network,
        asset_id: Number(id),
        name: p.name,
        unit_name: p['unit-name'],
        decimals: p.decimals,
        total: p.decimals ? Number(p.total) / 10 ** p.decimals : p.total,
        creator: p.creator,
        url: p.url,
        default_frozen: p['default-frozen'],
      };
    }
    case 'application': {
      const id = need(input.id, 'id', 'application id');
      const { params: p } = await getJson(`${algod}/v2/applications/${id}`, options.signal);
      return {
        network,
        application_id: Number(id),
        creator: p.creator,
        approval_program_bytes: Buffer.from(p['approval-program'] ?? '', 'base64').length,
        global_state_schema: p['global-state-schema'],
        local_state_schema: p['local-state-schema'],
        global_state: decodeState(p['global-state']),
      };
    }
    case 'transaction': {
      const txid = need(input.txid, TXID, 'transaction id');
      const { transaction: t } = await getJson(`${indexer}/v2/transactions/${txid}`, options.signal);
      return { network, ...summarizeTransaction(t) };
    }
    case 'account_transactions': {
      const address = need(input.address, ADDRESS, 'address');
      const limit = Math.min(Math.max(Number(input.limit) || 10, 1), 50);
      const r = await getJson(`${indexer}/v2/accounts/${address}/transactions?limit=${limit}`, options.signal);
      return { network, address, transactions: (r.transactions ?? []).map(summarizeTransaction) };
    }
  }
}

function summarizeTransaction(t: any): Record<string, unknown> {
  const pay = t['payment-transaction'];
  const axfer = t['asset-transfer-transaction'];
  const appl = t['application-transaction'];
  return {
    id: t.id,
    type: t['tx-type'],
    round: t['confirmed-round'],
    time: t['round-time'] ? new Date(t['round-time'] * 1000).toISOString() : undefined,
    sender: t.sender,
    fee_algo: (t.fee ?? 0) / MICRO,
    ...(pay ? { receiver: pay.receiver, amount_algo: pay.amount / MICRO } : {}),
    ...(axfer ? { receiver: axfer.receiver, asset_id: axfer['asset-id'], amount_base_units: axfer.amount } : {}),
    ...(appl ? { application_id: appl['application-id'], on_completion: appl['on-completion'] } : {}),
    note: t.note ? printable(Buffer.from(t.note, 'base64')) ?? '(binary note)' : undefined,
  };
}
