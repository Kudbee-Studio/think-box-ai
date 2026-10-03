import { test } from 'node:test';
import assert from 'node:assert/strict';
import { htmlToText } from '../agent.ts';

test('htmlToText drops script and style blocks even when the end tag has spaces or attributes', () => {
  assert.equal(htmlToText('a<script>alert(1)</script >b'), 'a b');
  assert.equal(htmlToText('a<script>alert(1)</script foo="bar">b'), 'a b');
  assert.equal(htmlToText('a<style>p{color:red}</style\t>b'), 'a b');
});

test('htmlToText decodes an entity once: &amp;lt; stays the text "&lt;", it does not become "<"', () => {
  assert.equal(htmlToText('&amp;lt;b&amp;gt;'), '&lt;b&gt;');
  assert.equal(htmlToText('1 &lt; 2 &amp; 3 &gt; 2'), '1 < 2 & 3 > 2');
});
