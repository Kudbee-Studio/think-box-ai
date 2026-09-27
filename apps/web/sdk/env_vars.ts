/**
 * Hermetic env profile labels for Kudbee web SDK (PR #200).
 * No secrets — mirrors thinkbox/env_vars/profile.py.
 */

export type EnvProfile = "dev" | "test" | "ci" | "hermetic";

export const ENV_VARS_GATE_ID = "environmental-variables";
export const ENV_VARS_PR_NUMBER = 200;

export function detectEnvProfile(env: Record<string, string>): EnvProfile {
  if ((env.CI || "").toLowerCase() === "true" || env.CI === "1") {
    return "ci";
  }
  if ((env.THINKBOX_KILO_HERMETIC_MODE || "").toLowerCase() === "true") {
    return "hermetic";
  }
  if (env.PYTEST_CURRENT_TEST) {
    return "test";
  }
  return "dev";
}

export function envPackHonesty(): {
  live_verified: false;
  live_api_called: false;
  four_state_max: "TEST_VERIFIED";
} {
  return {
    live_verified: false,
    live_api_called: false,
    four_state_max: "TEST_VERIFIED",
  };
}
