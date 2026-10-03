# CodeQL (local) - fix/frontend-xss-sweep

javascript-code-scanning suite on a clean clone of the PR commit; baseline = main after #351 (8 alerts, all documented false positives).

Result: 8 alerts, 0 new.

- js/missing-rate-limiting server.ts:178
- js/missing-rate-limiting server.ts:2026
- js/path-injection server.ts:237
- js/path-injection server.ts:2031
- js/path-injection server.ts:2035
- js/path-injection server.ts:2040
- js/path-injection workspace-fs.ts:39
- js/request-forgery algorand.ts:49
