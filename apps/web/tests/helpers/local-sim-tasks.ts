// FROZEN task set for the P3.48 experiment (docs/evidence/p3.48-local-simulate/PLAN.md). Each task is a tiny git repository with ONE genuinely failing test and a goal in plain English;
// `ref` is a reference fix (exact text edits) used only by the pre-flight to prove the task is fixable and the test really flips from failing to passing. Models never see `ref` or the
// test's expected values unless they read the test file. Changing anything here changes the hash recorded in the results: do not edit after the first run.
export interface Edit { path: string; find?: string; replace?: string; create?: string }
export interface Task { id: string; kind: string; goal: string; files: Record<string, string>; ref: Edit[] }

const W = 'apps/web';
const t = (name: string, requireLine: string, body: string): string => `const { test } = require('node:test'); const assert = require('node:assert');\n${requireLine}\ntest('${name}', () => { ${body} });\n`;

export const TASKS: Task[] = [
  { id: 'T01', kind: 'typo, file named', goal: "The greeting test in apps/web/tests/greeter.test.js fails because greet() says 'helo' instead of 'hello'. Fix it.",
    files: { [`${W}/src/greeter.js`]: "function greet(name) {\n  return 'helo ' + name;\n}\nmodule.exports = { greet };\n", [`${W}/tests/greeter.test.js`]: t('greets', "const { greet } = require('../src/greeter.js');", "assert.equal(greet('x'), 'hello x');") },
    ref: [{ path: `${W}/src/greeter.js`, find: "'helo '", replace: "'hello '" }] },
  { id: 'T02', kind: 'off by one, file named', goal: 'sumTo(5) should return 15 but returns 10. Fix sumTo in apps/web/src/sum.js.',
    files: { [`${W}/src/sum.js`]: 'function sumTo(n) {\n  let total = 0;\n  for (let i = 1; i < n; i++) {\n    total += i;\n  }\n  return total;\n}\nmodule.exports = { sumTo };\n', [`${W}/tests/sum.test.js`]: t('sums', "const { sumTo } = require('../src/sum.js');", 'assert.equal(sumTo(5), 15); assert.equal(sumTo(1), 1);') },
    ref: [{ path: `${W}/src/sum.js`, find: 'i < n', replace: 'i <= n' }] },
  { id: 'T03', kind: 'wrong operator, file not named', goal: 'add(2, 3) returns -1 instead of 5. Fix it.',
    files: { [`${W}/src/math.js`]: 'function add(a, b) {\n  return a - b;\n}\nfunction multiply(a, b) {\n  return a * b;\n}\nmodule.exports = { add, multiply };\n', [`${W}/src/strings.js`]: "function shout(s) {\n  return s.toUpperCase() + '!';\n}\nmodule.exports = { shout };\n", [`${W}/tests/math.test.js`]: t('adds', "const { add, multiply } = require('../src/math.js');", 'assert.equal(add(2, 3), 5); assert.equal(multiply(2, 3), 6);') },
    ref: [{ path: `${W}/src/math.js`, find: 'return a - b;', replace: 'return a + b;' }] },
  { id: 'T04', kind: 'boundary, file not named', goal: 'isAdult(18) should be true but returns false. Fix it.',
    files: { [`${W}/src/age.js`]: 'function isAdult(age) {\n  return age > 18;\n}\nmodule.exports = { isAdult };\n', [`${W}/src/name.js`]: "function initials(first, last) {\n  return first[0] + last[0];\n}\nmodule.exports = { initials };\n", [`${W}/tests/age.test.js`]: t('adult at 18', "const { isAdult } = require('../src/age.js');", 'assert.equal(isAdult(18), true); assert.equal(isAdult(17), false);') },
    ref: [{ path: `${W}/src/age.js`, find: 'age > 18', replace: 'age >= 18' }] },
  { id: 'T05', kind: 'missing return', goal: 'total([1, 2, 3]) returns undefined instead of 6. Fix it.',
    files: { [`${W}/src/total.js`]: 'function total(items) {\n  let sum = 0;\n  for (const item of items) {\n    sum += item;\n  }\n}\nmodule.exports = { total };\n', [`${W}/tests/total.test.js`]: t('totals', "const { total } = require('../src/total.js');", 'assert.equal(total([1, 2, 3]), 6); assert.equal(total([]), 0);') },
    ref: [{ path: `${W}/src/total.js`, find: '    sum += item;\n  }\n}', replace: '    sum += item;\n  }\n  return sum;\n}' }] },
  { id: 'T06', kind: 'wrong default value', goal: 'withTax(100) should return 125 because the default tax rate is 25%, but it returns 120. Fix it.',
    files: { [`${W}/src/price.js`]: 'function withTax(price, rate = 0.2) {\n  return price * (1 + rate);\n}\nmodule.exports = { withTax };\n', [`${W}/tests/price.test.js`]: t('tax', "const { withTax } = require('../src/price.js');", 'assert.equal(withTax(100), 125); assert.equal(withTax(100, 0.1), 110.00000000000001);') },
    ref: [{ path: `${W}/src/price.js`, find: 'rate = 0.2', replace: 'rate = 0.25' }] },
  { id: 'T07', kind: 'case sensitivity', goal: "sameName('Ann', 'ann') should be true because names are compared ignoring case. Fix it.",
    files: { [`${W}/src/names.js`]: 'function sameName(a, b) {\n  return a === b;\n}\nmodule.exports = { sameName };\n', [`${W}/tests/names.test.js`]: t('same name', "const { sameName } = require('../src/names.js');", "assert.equal(sameName('Ann', 'ann'), true); assert.equal(sameName('Ann', 'Bob'), false);") },
    ref: [{ path: `${W}/src/names.js`, find: 'return a === b;', replace: 'return a.toLowerCase() === b.toLowerCase();' }] },
  { id: 'T08', kind: 'index bug', goal: 'last([1, 2, 3]) returns undefined instead of 3. Fix it.',
    files: { [`${W}/src/last.js`]: 'function last(arr) {\n  return arr[arr.length];\n}\nmodule.exports = { last };\n', [`${W}/tests/last.test.js`]: t('last', "const { last } = require('../src/last.js');", "assert.equal(last([1, 2, 3]), 3); assert.equal(last(['a']), 'a');") },
    ref: [{ path: `${W}/src/last.js`, find: 'arr[arr.length]', replace: 'arr[arr.length - 1]' }] },
  { id: 'T09', kind: 'swapped arguments', goal: 'ratio(10, 4) should be 2.5 but returns 0.4. Fix it.',
    files: { [`${W}/src/ratio.js`]: 'function divide(a, b) {\n  return a / b;\n}\nfunction ratio(x, y) {\n  return divide(y, x);\n}\nmodule.exports = { divide, ratio };\n', [`${W}/tests/ratio.test.js`]: t('ratio', "const { ratio } = require('../src/ratio.js');", 'assert.equal(ratio(10, 4), 2.5);') },
    ref: [{ path: `${W}/src/ratio.js`, find: 'divide(y, x)', replace: 'divide(x, y)' }] },
  { id: 'T10', kind: 'search among several files', goal: "capitalize('hello') returns 'Hllo' instead of 'Hello'. Fix it.",
    files: { [`${W}/src/strings.js`]: 'function capitalize(s) {\n  return s[0].toUpperCase() + s.slice(2);\n}\nfunction reverse(s) {\n  return s.split(\'\').reverse().join(\'\');\n}\nmodule.exports = { capitalize, reverse };\n', [`${W}/src/numbers.js`]: 'function clamp(n, lo, hi) {\n  return Math.min(hi, Math.max(lo, n));\n}\nmodule.exports = { clamp };\n', [`${W}/src/lists.js`]: 'function unique(xs) {\n  return [...new Set(xs)];\n}\nmodule.exports = { unique };\n', [`${W}/src/dates.js`]: 'function year(d) {\n  return new Date(d).getUTCFullYear();\n}\nmodule.exports = { year };\n', [`${W}/tests/strings.test.js`]: t('capitalize', "const { capitalize, reverse } = require('../src/strings.js');", "assert.equal(capitalize('hello'), 'Hello'); assert.equal(reverse('ab'), 'ba');") },
    ref: [{ path: `${W}/src/strings.js`, find: 's.slice(2)', replace: 's.slice(1)' }] },
  { id: 'T11', kind: 'two files, bug in the one not named', goal: "formatPrice(1.5) should give '$1.50' but gives '$0.15'. Fix it.",
    files: { [`${W}/src/money.js`]: 'function toCents(dollars) {\n  return Math.round(dollars * 10);\n}\nmodule.exports = { toCents };\n', [`${W}/src/format.js`]: "const { toCents } = require('./money.js');\nfunction formatPrice(dollars) {\n  const cents = toCents(dollars);\n  return '$' + (cents / 100).toFixed(2);\n}\nmodule.exports = { formatPrice };\n", [`${W}/tests/format.test.js`]: t('format', "const { formatPrice } = require('../src/format.js');", "assert.equal(formatPrice(1.5), '$1.50'); assert.equal(formatPrice(20), '$20.00');") },
    ref: [{ path: `${W}/src/money.js`, find: 'dollars * 10', replace: 'dollars * 100' }] },
  { id: 'T12', kind: 'edge case', goal: 'average([]) returns NaN. It should return 0 for an empty list. Fix it.',
    files: { [`${W}/src/avg.js`]: 'function average(xs) {\n  let sum = 0;\n  for (const x of xs) {\n    sum += x;\n  }\n  return sum / xs.length;\n}\nmodule.exports = { average };\n', [`${W}/tests/avg.test.js`]: t('average', "const { average } = require('../src/avg.js');", 'assert.equal(average([2, 4]), 3); assert.equal(average([]), 0);') },
    ref: [{ path: `${W}/src/avg.js`, find: '  let sum = 0;', replace: '  if (xs.length === 0) return 0;\n  let sum = 0;' }] },
  { id: 'T13', kind: 'add a function', goal: 'Add a function double(n) to apps/web/src/mathx.js that returns n times 2, and export it.',
    files: { [`${W}/src/mathx.js`]: 'function triple(n) {\n  return n * 3;\n}\nmodule.exports = { triple };\n', [`${W}/tests/mathx.test.js`]: t('mathx', "const { triple, double } = require('../src/mathx.js');", 'assert.equal(triple(2), 6); assert.equal(double(4), 8);') },
    ref: [{ path: `${W}/src/mathx.js`, find: 'module.exports = { triple };', replace: 'function double(n) {\n  return n * 2;\n}\nmodule.exports = { triple, double };' }] },
  { id: 'T14', kind: 'missing export', goal: 'slugify is defined in apps/web/src/util.js but require() does not return it, so the slug test fails. Fix it.',
    files: { [`${W}/src/util.js`]: "function trim(s) {\n  return s.trim();\n}\nfunction slugify(s) {\n  return s.trim().toLowerCase().split(' ').join('-');\n}\nmodule.exports = { trim };\n", [`${W}/tests/util.test.js`]: t('slugify', "const { slugify } = require('../src/util.js');", "assert.equal(slugify(' Hello World '), 'hello-world');") },
    ref: [{ path: `${W}/src/util.js`, find: 'module.exports = { trim };', replace: 'module.exports = { trim, slugify };' }] },
  { id: 'T15', kind: 'only the first match is replaced', goal: "removeSpaces('a b c') returns 'ab c' instead of 'abc'. Fix it.",
    files: { [`${W}/src/spaces.js`]: "function removeSpaces(s) {\n  return s.replace(' ', '');\n}\nmodule.exports = { removeSpaces };\n", [`${W}/tests/spaces.test.js`]: t('spaces', "const { removeSpaces } = require('../src/spaces.js');", "assert.equal(removeSpaces('a b c'), 'abc'); assert.equal(removeSpaces(' x '), 'x');") },
    ref: [{ path: `${W}/src/spaces.js`, find: "s.replace(' ', '')", replace: "s.split(' ').join('')" }] },
];

export const PACKAGE_JSON = JSON.stringify({ name: 'fixture', scripts: { test: 'node --test "tests/*.test.js"', lint: 'node -e "0"' } });
