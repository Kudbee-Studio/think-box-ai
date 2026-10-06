// FROZEN HARD task set for the P3.50 cloud-model experiment (docs/evidence/p3.50-hard-tasks/PLAN.md). Same shape as local-sim-tasks.ts: each task is a tiny git repository with ONE failing test file and a
// goal in plain English; `ref` is a reference fix used only by the pre-flight. Written BEFORE any run on it, and not tuned afterwards: do not edit after the first run (the hash is recorded in the results).
// These are harder than the P3.48 set: symptom-only goals, a bug in a different file from the symptom, fixes that need several lines, and one fix that needs edits in two files.
import { PACKAGE_JSON } from './local-sim-tasks.ts';
import type { Edit, Task } from './local-sim-tasks.ts';

const W = 'apps/web';
const lines = (...l: string[]): string => `${l.join('\n')}\n`;
const head = "const { test } = require('node:test'); const assert = require('node:assert');";

export const TASKS: Task[] = [
  { id: 'H01', kind: 'one-based pages, symptom only', goal: 'Page 1 of the paginated list shows the second chunk of items instead of the first. Pages are numbered from 1. Fix it.',
    files: {
      [`${W}/src/paginate.js`]: lines('function paginate(items, page, size) {', '  const start = page * size;', '  return items.slice(start, start + size);', '}', 'function pageCount(items, size) {', '  return Math.ceil(items.length / size);', '}', 'module.exports = { paginate, pageCount };'),
      [`${W}/tests/paginate.test.js`]: lines(head, "const { paginate, pageCount } = require('../src/paginate.js');", "test('first page', () => { assert.deepEqual(paginate([1, 2, 3, 4, 5], 1, 2), [1, 2]); });", "test('last page', () => { assert.deepEqual(paginate([1, 2, 3, 4, 5], 3, 2), [5]); });", "test('count', () => { assert.equal(pageCount([1, 2, 3, 4, 5], 2), 3); });"),
    }, ref: [{ path: `${W}/src/paginate.js`, find: 'page * size', replace: '(page - 1) * size' }] },
  { id: 'H02', kind: 'sort: direction, tie-break and no mutation', goal: 'rank(players) should return players sorted by score, highest first, and by name A to Z when scores are equal, without changing the array it was given. Right now the order is wrong.',
    files: {
      [`${W}/src/rank.js`]: lines('function rank(players) {', '  return players.sort((a, b) => a.score - b.score);', '}', 'module.exports = { rank };'),
      [`${W}/tests/rank.test.js`]: lines(head, "const { rank } = require('../src/rank.js');", "const input = [{ name: 'bo', score: 5 }, { name: 'al', score: 9 }, { name: 'cy', score: 5 }];", "test('order and ties', () => { assert.deepEqual(rank(input).map((p) => p.name), ['al', 'bo', 'cy']); });", "test('input untouched', () => { rank(input); assert.deepEqual(input.map((p) => p.name), ['bo', 'al', 'cy']); });"),
    }, ref: [{ path: `${W}/src/rank.js`, find: 'players.sort((a, b) => a.score - b.score)', replace: '[...players].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name))' }] },
  { id: 'H03', kind: 'defaults override the caller and mutate', goal: 'withDefaults(opts) is supposed to fill in missing settings but keep the values the caller gave. Instead the defaults overwrite the caller\'s values, and the object passed in gets changed. Fix it.',
    files: {
      [`${W}/src/options.js`]: lines('const DEFAULTS = { retries: 3, verbose: false };', 'function withDefaults(opts) {', '  return Object.assign(opts, DEFAULTS);', '}', 'module.exports = { withDefaults, DEFAULTS };'),
      [`${W}/tests/options.test.js`]: lines(head, "const { withDefaults } = require('../src/options.js');", "test('keeps caller values', () => { assert.deepEqual(withDefaults({ retries: 7 }), { retries: 7, verbose: false }); });", "test('does not mutate', () => { const o = { verbose: true }; withDefaults(o); assert.deepEqual(o, { verbose: true }); });"),
    }, ref: [{ path: `${W}/src/options.js`, find: 'Object.assign(opts, DEFAULTS)', replace: 'Object.assign({}, DEFAULTS, opts)' }] },
  { id: 'H04', kind: 'cache key ignores later arguments', goal: 'The memoized function returns a stale answer: calling it with the same first argument but a different second argument gives the first answer again. Fix the memoization.',
    files: {
      [`${W}/src/memo.js`]: lines('function memoize(fn) {', '  const cache = new Map();', '  return (...args) => {', '    const key = args[0];', '    if (!cache.has(key)) cache.set(key, fn(...args));', '    return cache.get(key);', '  };', '}', 'module.exports = { memoize };'),
      [`${W}/tests/memo.test.js`]: lines(head, "const { memoize } = require('../src/memo.js');", "test('keys on all arguments', () => { const add = memoize((a, b) => a + b); assert.equal(add(1, 2), 3); assert.equal(add(1, 3), 4); });", "test('still caches', () => { let calls = 0; const f = memoize((a, b) => { calls += 1; return a + b; }); f(1, 2); f(1, 2); assert.equal(calls, 1); });"),
    }, ref: [{ path: `${W}/src/memo.js`, find: 'const key = args[0];', replace: 'const key = JSON.stringify(args);' }] },
  { id: 'H05', kind: 'async: promises not awaited', goal: 'loadAll(ids, fetchOne) should resolve to the list of results, but the callers get a list of Promise objects. Fix it.',
    files: {
      [`${W}/src/loader.js`]: lines('async function loadAll(ids, fetchOne) {', '  return ids.map((id) => fetchOne(id));', '}', 'module.exports = { loadAll };'),
      [`${W}/tests/loader.test.js`]: lines(head, "const { loadAll } = require('../src/loader.js');", "test('resolves values', async () => { const out = await loadAll([1, 2, 3], async (id) => id * 10); assert.deepEqual(out, [10, 20, 30]); });"),
    }, ref: [{ path: `${W}/src/loader.js`, find: 'return ids.map((id) => fetchOne(id));', replace: 'return Promise.all(ids.map((id) => fetchOne(id)));' }] },
  { id: 'H06', kind: 'regex too permissive', goal: "isEmail('a@b') returns true but it must be false: an address needs a dot in the part after the @. Fix isEmail without breaking the valid cases.",
    files: {
      [`${W}/src/validate.js`]: lines('function isEmail(s) {', '  return /^[^@\\s]+@[^@\\s]+$/.test(s);', '}', 'function isPhone(s) {', '  return /^\\d{10}$/.test(s);', '}', 'module.exports = { isEmail, isPhone };'),
      [`${W}/tests/validate.test.js`]: lines(head, "const { isEmail } = require('../src/validate.js');", "test('valid', () => { assert.equal(isEmail('a@b.co'), true); assert.equal(isEmail('x.y@mail.example.org'), true); });", "test('invalid', () => { assert.equal(isEmail('a@b'), false); assert.equal(isEmail('a@@b.co'), false); assert.equal(isEmail('a b@c.co'), false); assert.equal(isEmail('nope'), false); });"),
    }, ref: [{ path: `${W}/src/validate.js`, find: '/^[^@\\s]+@[^@\\s]+$/', replace: '/^[^@\\s]+@[^@\\s.]+(\\.[^@\\s.]+)+$/' }] },
  { id: 'H07', kind: 'rename across two files (two edits)', goal: 'Rename the function fetchUser to getUser everywhere under apps/web/src: its definition and the place that calls it. The tests already use the new name.',
    files: {
      [`${W}/src/users.js`]: lines('const USERS = { 1: { name: "ann" }, 2: { name: "bob" } };', 'function fetchUser(id) {', '  return USERS[id] || null;', '}', 'module.exports = { fetchUser };'),
      [`${W}/src/greeting.js`]: lines("const { fetchUser } = require('./users.js');", 'function greetUser(id) {', '  const u = fetchUser(id);', "  return u ? 'hi ' + u.name : 'hi stranger';", '}', 'module.exports = { greetUser };'),
      [`${W}/tests/users.test.js`]: lines(head, "const { getUser } = require('../src/users.js'); const { greetUser } = require('../src/greeting.js');", "test('getUser', () => { assert.equal(getUser(1).name, 'ann'); });", "test('greetUser', () => { assert.equal(greetUser(2), 'hi bob'); assert.equal(greetUser(9), 'hi stranger'); });"),
    }, ref: [{ path: `${W}/src/users.js`, find: 'function fetchUser(id)', replace: 'function getUser(id)' }, { path: `${W}/src/users.js`, find: 'module.exports = { fetchUser };', replace: 'module.exports = { getUser };' }, { path: `${W}/src/greeting.js`, find: "const { fetchUser } = require('./users.js');", replace: "const { getUser } = require('./users.js');" }, { path: `${W}/src/greeting.js`, find: 'const u = fetchUser(id);', replace: 'const u = getUser(id);' }] },
  { id: 'H08', kind: 'LRU: reading must refresh recency', goal: 'The small cache evicts the wrong entry: an entry that was just read should count as recently used, so it must not be the one thrown out when the cache is full. Fix it.',
    files: {
      [`${W}/src/lru.js`]: lines('class Lru {', '  constructor(cap) { this.cap = cap; this.map = new Map(); }', '  get(key) {', '    return this.map.get(key);', '  }', '  set(key, value) {', '    this.map.delete(key);', '    this.map.set(key, value);', '    if (this.map.size > this.cap) this.map.delete(this.map.keys().next().value);', '  }', '}', 'module.exports = { Lru };'),
      [`${W}/tests/lru.test.js`]: lines(head, "const { Lru } = require('../src/lru.js');", "test('read refreshes', () => { const c = new Lru(2); c.set('a', 1); c.set('b', 2); c.get('a'); c.set('c', 3); assert.equal(c.get('a'), 1); assert.equal(c.get('b'), undefined); assert.equal(c.get('c'), 3); });", "test('miss', () => { assert.equal(new Lru(1).get('x'), undefined); });"),
    }, ref: [{ path: `${W}/src/lru.js`, find: '    return this.map.get(key);', replace: '    if (!this.map.has(key)) return undefined;\n    const v = this.map.get(key);\n    this.map.delete(key);\n    this.map.set(key, v);\n    return v;' }] },
  { id: 'H09', kind: 'modulo missing', goal: "formatDuration(3725) should give '1h 2m 5s' but gives '1h 62m 3725s'. Fix it.",
    files: {
      [`${W}/src/duration.js`]: lines('function formatDuration(total) {', '  const h = Math.floor(total / 3600);', '  const m = Math.floor(total / 60);', '  const s = total;', "  return h + 'h ' + m + 'm ' + s + 's';", '}', 'module.exports = { formatDuration };'),
      [`${W}/tests/duration.test.js`]: lines(head, "const { formatDuration } = require('../src/duration.js');", "test('hms', () => { assert.equal(formatDuration(3725), '1h 2m 5s'); assert.equal(formatDuration(59), '0h 0m 59s'); assert.equal(formatDuration(3600), '1h 0m 0s'); });"),
    }, ref: [{ path: `${W}/src/duration.js`, find: '  const m = Math.floor(total / 60);\n  const s = total;', replace: '  const m = Math.floor((total % 3600) / 60);\n  const s = total % 60;' }] },
  { id: 'H10', kind: 'missing validation (new behaviour)', goal: "parseAge('abc') returns NaN. It should throw a RangeError whose message contains 'invalid age'. The same goes for negative numbers and for anything over 150. Valid ages still return the number.",
    files: {
      [`${W}/src/age.js`]: lines('function parseAge(text) {', '  return Number(text);', '}', 'module.exports = { parseAge };'),
      [`${W}/tests/age.test.js`]: lines(head, "const { parseAge } = require('../src/age.js');", "test('valid', () => { assert.equal(parseAge('42'), 42); assert.equal(parseAge('0'), 0); assert.equal(parseAge('150'), 150); });", "test('invalid', () => { for (const bad of ['abc', '-1', '151', '']) assert.throws(() => parseAge(bad), (e) => e instanceof RangeError && /invalid age/.test(e.message)); });"),
    }, ref: [{ path: `${W}/src/age.js`, find: '  return Number(text);', replace: "  const n = Number(text);\n  if (text === '' || !Number.isFinite(n) || n < 0 || n > 150) throw new RangeError('invalid age: ' + text);\n  return n;" }] },
  { id: 'H11', kind: 'symptom only, bug among distractors', goal: 'The cart total is wrong when an item is bought more than once: two of the same item are only charged once. Fix the total.',
    files: {
      [`${W}/src/cart.js`]: lines("const { applyDiscount } = require('./discount.js');", 'function subtotal(items) {', '  return items.reduce((sum, it) => sum + it.price, 0);', '}', 'function total(items, code) {', '  return applyDiscount(subtotal(items), code);', '}', 'module.exports = { subtotal, total };'),
      [`${W}/src/discount.js`]: lines('function applyDiscount(amount, code) {', "  return code === 'HALF' ? amount / 2 : amount;", '}', 'module.exports = { applyDiscount };'),
      [`${W}/tests/cart.test.js`]: lines(head, "const { total } = require('../src/cart.js');", "test('quantity counts', () => { assert.equal(total([{ price: 10, qty: 2 }, { price: 5, qty: 1 }]), 25); });", "test('discount still applies', () => { assert.equal(total([{ price: 10, qty: 2 }], 'HALF'), 10); });"),
    }, ref: [{ path: `${W}/src/cart.js`, find: 'sum + it.price', replace: 'sum + it.price * it.qty' }] },
  { id: 'H12', kind: 'mutates its input', goal: 'removeAt(list, index) is meant to return a new list without that item, but it also changes the list that was passed in. Fix it.',
    files: {
      [`${W}/src/lists.js`]: lines('function removeAt(list, index) {', '  list.splice(index, 1);', '  return list;', '}', 'module.exports = { removeAt };'),
      [`${W}/tests/lists.test.js`]: lines(head, "const { removeAt } = require('../src/lists.js');", "test('returns the rest', () => { assert.deepEqual(removeAt(['a', 'b', 'c'], 1), ['a', 'c']); });", "test('leaves the input alone', () => { const l = ['a', 'b', 'c']; removeAt(l, 0); assert.deepEqual(l, ['a', 'b', 'c']); });"),
    }, ref: [{ path: `${W}/src/lists.js`, find: '  list.splice(index, 1);\n  return list;', replace: '  return list.filter((_, i) => i !== index);' }] },
];
export { PACKAGE_JSON };
export type { Edit };
