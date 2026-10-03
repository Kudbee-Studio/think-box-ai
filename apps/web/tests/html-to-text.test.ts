import { test } from 'node:test';
import assert from 'node:assert/strict';
import { htmlToText } from '../agent.ts';

test('htmlToText drops script and style blocks even when the end tag has spaces or attributes', () => {
  assert.equal(htmlToText('a<script>alert(1)</script >b'), 'a b');
  assert.equal(htmlToText('a<script>alert(1)</script foo="bar">b'), 'a b');
  assert.equal(htmlToText('a<style>p{color:red}</style\t>b'), 'a b');
});
