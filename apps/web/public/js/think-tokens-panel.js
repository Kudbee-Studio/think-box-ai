// Think Tokens panel (ADR 028): list, search, accept/retire, thumbs, score, and which runs used each token.
// Rendered with createElement + textContent only; token text is data and never reaches innerHTML.
// Mutations are sent as think_token_action; the server asks for approval (the normal approval modal) before applying.
(function () {
  const $ = (id) => document.getElementById(id);
  let searchTimer = null;
  const pending = new Set();

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function request() {
    const message = { type: 'think_tokens_list', limit: 50 };
    const query = $('think-tokens-search').value.trim().slice(0, 100);
    const status = $('think-tokens-status').value;
    if (query) message.query = query;
    if (status) message.status = status;
    sendThinkTokenMessage(message);
  }

  function action(id, name) {
    pending.add(id);
    sendThinkTokenMessage({ type: 'think_token_action', action: name, id });
    $('think-tokens-meta').textContent = 'Waiting for your approval…';
  }

  function button(label, id, name, title) {
    const b = el('button', 'btn-secondary tt-btn', label);
    b.type = 'button';
    b.title = title;
    b.addEventListener('click', () => action(id, name));
    return b;
  }

  function card(token) {
    const root = el('article', `tt-card tt-${token.status}`);
    const head = el('div', 'tt-head');
    head.append(el('span', 'tt-kind', token.kind.replace('_', ' ')), el('strong', 'tt-title', token.title), el('span', `tt-status ${token.status}`, token.status));
    const score = el('span', 'tt-score', `score ${token.score.toFixed(2)}`);
    score.title = '0.45 usefulness + 0.20 recency + 0.15 reuse + 0.20 feedback';
    head.append(score);
    root.append(head, el('p', 'tt-content', token.content));

    const meta = el('div', 'tt-meta');
    meta.append(el('code', '', token.id), el('span', '', `uses ${token.uses}`), el('span', '', `👍 ${token.thumbs_up} 👎 ${token.thumbs_down}`), el('span', '', `evidence ${token.evidence_ref}`));
    if (token.tags.length) meta.append(el('span', 'tt-tags', token.tags.join(' · ')));
    root.append(meta);

    const used = el('div', 'tt-used');
    if (token.used_by && token.used_by.length) {
      used.append(el('span', '', 'Used by runs: '));
      for (const use of token.used_by) {
        const outcome = use.success === 1 ? ' ✓' : use.success === 0 ? ' ✗' : '';
        used.append(el('code', '', `${String(use.run_id).slice(0, 8)}${outcome}`));
      }
    } else {
      used.textContent = 'Not used by any run yet';
    }
    root.append(used);

    const actions = el('div', 'tt-actions');
    if (token.status !== 'accepted') actions.append(button('Accept', token.id, 'accept', 'Make this token eligible for planner context'));
    if (token.status !== 'retired') actions.append(button('Retire', token.id, 'retire', 'Stop using this token'));
    actions.append(button('👍', token.id, 'thumb_up', 'Helpful'), button('👎', token.id, 'thumb_down', 'Not helpful'));
    root.append(actions);
    return root;
  }

  function render(data) {
    const list = $('think-tokens-list');
    list.replaceChildren();
    if (!data.tokens.length) list.append(el('div', 'empty-state', 'No Think Tokens yet. Successful agent runs save candidates here for you to accept.'));
    for (const token of data.tokens) list.append(card(token));
    const ledger = data.ledger || {};
    $('think-tokens-meta').textContent = `${data.tokens.length} shown · write ledger ${ledger.ok ? 'verified' : 'BROKEN'} (${ledger.entries ?? 0} entries)`;
  }

  window.addEventListener('think-tokens:message', (event) => {
    const msg = event.detail;
    if (msg.type === 'think_tokens') render(msg.data);
    else if (msg.type === 'think_tokens_changed') { if (!$('think-tokens-modal').hidden) request(); }
    else if (msg.type === 'think_token_result') {
      pending.delete(msg.data.id);
      $('think-tokens-meta').textContent = msg.data.ok ? `Applied ${msg.data.action} (receipt ${msg.data.receipt?.receipt_id ?? 'n/a'})` : `Not applied: ${msg.data.error}`;
      request();
    } else if (msg.type === 'think_token_error') $('think-tokens-meta').textContent = `Rejected: ${msg.data.error}`;
  });

  document.addEventListener('DOMContentLoaded', () => {
    $('think-tokens-open').addEventListener('click', () => { $('think-tokens-modal').hidden = false; request(); });
    $('think-tokens-close').addEventListener('click', () => { $('think-tokens-modal').hidden = true; });
    $('think-tokens-status').addEventListener('change', request);
    $('think-tokens-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(request, 250); });
  });
}());
