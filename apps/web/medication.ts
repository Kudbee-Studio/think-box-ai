// Read-only medication label lookups through the public openFDA API (no key, no SDK).
// This module deliberately does NOT compute or assert whether two drugs interact — it
// surfaces each drug's own FDA-approved label sections (drug_interactions, boxed_warning,
// contraindications, warnings_and_cautions) so a human (ideally a pharmacist or physician)
// can compare them. Presenting a computed "safe" / "dangerous together" verdict from label
// text alone would be a false authority: the label for drug A does not know drug B exists.
import { setTimeout as delay } from 'node:timers/promises';

const OPENFDA_BASE_URL = 'https://api.fda.gov/drug/label.json';
const RXNAV_BASE_URL = 'https://rxnav.nlm.nih.gov/REST';

export const MEDICATION_SECTIONS = ['drug_interactions', 'boxed_warning', 'contraindications', 'warnings_and_cautions'] as const;
export type MedicationSection = (typeof MEDICATION_SECTIONS)[number];

export const MEDICATION_ACTIONS = ['lookup', 'compare'] as const;
export type MedicationAction = (typeof MEDICATION_ACTIONS)[number];

// openFDA's own disclaimer, surfaced verbatim on every response so nothing downstream
// (agent, dashboard, CLI) can present this as validated medical guidance.
export const OPENFDA_DISCLAIMER =
  'Source: openFDA (FDA-approved drug labeling). "Do not rely on openFDA to make decisions ' +
  'regarding medical care... you should assume all results are unvalidated." This tool does ' +
  'not determine whether specific drugs interact — it surfaces each drug\'s own label text. ' +
  'Always consult a licensed pharmacist or physician before making any medication decision.';

export interface MedicationInput {
  action?: unknown;
  drug?: unknown;
  drugs?: unknown;
  section?: unknown;
}

function sanitizeDrugName(value: unknown, label = 'drug name'): string {
  const text = String(value ?? '').trim();
  if (!text) throw new Error(`${label} is required`);
  if (text.length > 100) throw new Error(`${label} is too long`);
  // openFDA search terms are Lucene-ish; keep this to characters a real drug name would
  // use so a crafted value can't widen the query syntax, not because this is code exec risk.
  if (!/^[A-Za-z0-9 .\-/]+$/.test(text)) throw new Error(`${label} contains unsupported characters`);
  return text;
}

export function parseAction(value: unknown): MedicationAction {
  const action = String(value ?? '');
  if (!(MEDICATION_ACTIONS as readonly string[]).includes(action)) throw new Error(`action must be one of: ${MEDICATION_ACTIONS.join(', ')}`);
  return action as MedicationAction;
}

function parseSection(value: unknown): MedicationSection {
  if (value === undefined) return 'drug_interactions';
  const section = String(value);
  if (!(MEDICATION_SECTIONS as readonly string[]).includes(section)) throw new Error(`section must be one of: ${MEDICATION_SECTIONS.join(', ')}`);
  return section as MedicationSection;
}

export function validateMedicationInput(input: MedicationInput): void {
  const action = parseAction(input.action);
  parseSection(input.section);
  if (action === 'lookup') sanitizeDrugName(input.drug, 'drug');
  if (action === 'compare') {
    const drugs = input.drugs;
    if (!Array.isArray(drugs) || drugs.length < 2) throw new Error('compare requires an array of 2 or more drug names');
    if (drugs.length > 5) throw new Error('compare supports at most 5 drugs per call');
    drugs.forEach((d, i) => sanitizeDrugName(d, `drugs[${i}]`));
  }
}

async function getJson(url: string, signal?: AbortSignal): Promise<any> {
  const response = await fetch(url, { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000) });
  const body = await response.json().catch(() => ({})) as any;
  if (response.status === 404) return null; // openFDA: no matching label
  if (!response.ok) throw new Error(`openFDA API HTTP ${response.status}: ${body?.error?.message ?? ''}`.trim());
  return body;
}

function truncate(text: string | undefined, max = 2000): string | undefined {
  if (!text) return text;
  return text.length > max ? `${text.slice(0, max)}… [truncated, see source_url for full label]` : text;
}

interface DrugLookupResult {
  drug: string;
  found: boolean;
  brand_name?: string;
  generic_name?: string;
  rxcui?: string[];
  section: MedicationSection;
  text?: string;
  total_matching_labels?: number;
  ambiguous?: boolean;
  source_url: string;
}

async function lookupOne(drug: string, section: MedicationSection, baseUrl: string, signal?: AbortSignal): Promise<DrugLookupResult> {
  const query = `(openfda.generic_name:"${drug}"+openfda.brand_name:"${drug}")`;
  const url = `${baseUrl}?search=${encodeURIComponent(query)}&limit=1`;
  const data = await getJson(url, signal);
  const total = data?.meta?.results?.total ?? 0;
  const result = data?.results?.[0];

  if (!result) {
    return { drug, found: false, section, total_matching_labels: 0, source_url: url };
  }

  return {
    drug,
    found: true,
    brand_name: result.openfda?.brand_name?.[0],
    generic_name: result.openfda?.generic_name?.[0],
    rxcui: result.openfda?.rxcui,
    section,
    text: truncate(result[section]?.[0]),
    total_matching_labels: total,
    // Many distinct approved products can share a generic name (different manufacturers,
    // strengths, combination products); this flags that the single label picked is one of several.
    ambiguous: total > 1,
    source_url: url,
  };
}

export async function medicationQuery(
  input: MedicationInput,
  options: { signal?: AbortSignal; openfdaBaseUrl?: string; interDrugDelayMs?: number } = {},
): Promise<Record<string, unknown>> {
  validateMedicationInput(input);
  const action = parseAction(input.action);
  const section = parseSection(input.section);
  const baseUrl = options.openfdaBaseUrl ?? OPENFDA_BASE_URL;
  const interDrugDelayMs = options.interDrugDelayMs ?? 150;

  if (action === 'lookup') {
    const drug = sanitizeDrugName(input.drug, 'drug');
    const result = await lookupOne(drug, section, baseUrl, options.signal);
    return { ...result, disclaimer: OPENFDA_DISCLAIMER };
  }

  // action === 'compare': fetch each drug's own label sections independently. Sequential with
  // a small delay, not Promise.all — openFDA's public (unauthenticated) rate limit is 40
  // requests/minute/IP, and a 5-drug compare already uses 5 of those.
  const drugs = (input.drugs as unknown[]).map((d) => sanitizeDrugName(d, 'drug'));
  const results: DrugLookupResult[] = [];
  for (const drug of drugs) {
    results.push(await lookupOne(drug, section, baseUrl, options.signal));
    if (drug !== drugs[drugs.length - 1]) await delay(interDrugDelayMs);
  }

  return {
    drugs: results,
    disclaimer: OPENFDA_DISCLAIMER,
    note:
      'Each entry is that drug\'s OWN label section — this call does not cross-reference them or ' +
      'compute whether they interact. Read each section for mentions of the other drug(s) or their ' +
      'drug class(es), and confirm with a pharmacist or physician before acting on this.',
  };
}

/** Resolves a drug name to RxNorm concept IDs (RxCUI) via RxNav — useful for cross-referencing
 *  with other RxNorm-based tools. Not used for interaction inference (that API was retired). */
export async function resolveRxcui(drug: string, signal?: AbortSignal): Promise<string[]> {
  const name = sanitizeDrugName(drug, 'drug');
  const url = `${RXNAV_BASE_URL}/rxcui.json?name=${encodeURIComponent(name)}`;
  const data = await getJson(url, signal);
  return data?.idGroup?.rxnormId ?? [];
}
