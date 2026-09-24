/** Enterprise long-range energy SDK surface (PR #195). */

import type { KudbeeSdkConfig } from './config.ts';

export const SDK_ENTERPRISE_LR_ENERGY_VERSION = '1.0.0-enterprise';

export type EnterpriseTier = 'standard' | 'business' | 'enterprise';

export function enterpriseCapabilityCatalog(): string[] {
  return [
    'tenant_isolation',
    'rbac',
    'sla_tiers',
    'compliance_receipts',
    'audit_trail',
    'data_residency',
    'governance_admission',
    'multi_region_routing',
    'enterprise_quotas',
    'soc2_mapping',
  ];
}

export async function fetchEnterpriseCapabilities(
  config: KudbeeSdkConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<{ capabilities: string[]; tier: EnterpriseTier; liveApiCalled: false }> {
  const res = await fetchImpl(`${config.baseUrl}/api/sdk/v6/enterprise-lr-energy/capabilities`, {
    headers: { accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`enterprise capabilities ${res.status}`);
  }
  const body = (await res.json()) as { capabilities?: string[]; tier?: EnterpriseTier };
  return {
    capabilities: body.capabilities ?? enterpriseCapabilityCatalog(),
    tier: body.tier ?? 'enterprise',
    liveApiCalled: false,
  };
}

export const enterpriseRouteCatalog = (): string[] => [
  '/api/health',
  '/api/sdk/v6/enterprise-lr-energy/capabilities',
  '/api/sdk/v6/enterprise-lr-energy/tenant/envelope',
  '/api/sdk/v6/enterprise-lr-energy/compliance/receipts',
  '/api/sdk/v6/enterprise-lr-energy/audit/trail',
];
