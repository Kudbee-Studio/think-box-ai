# P3.17: dashboard polish ("Invalid Date" and unstyled panels)

Founder asked for a polish pass on the Agent OS dashboard: the "Invalid Date" on thought cards and panels that look unstyled.

## "Invalid Date"

`app.js` built every thought as `{ ...msg.data, timestamp: msg.timestamp }`. The server stamps the timestamp inside `data` and sends no top-level one, so the spread overwrote a real number with `undefined` and the card printed "Invalid Date". Tasks had the identical line (`addTask({ ...msg.data, timestamp: msg.timestamp })`). Both now keep `data.timestamp` (then the message's, then now). A new `formatThoughtTime` shows a time of day, or nothing, for a missing or invalid timestamp, never the text "Invalid Date".

## Unstyled panels

45 component rules existed only in `css/main.css`, which `index.html` does not load: plugin badges and permission notes, task cards (priority, description, meta, tags, attachments, actions, activity, blocked reason), repository rows, thought header/type/content, generated images, overdue. They are ported into the loaded `polish.css` as they were, with two variable fixes for the live theme: `--border-color` -> `--border-light` and `--accent` -> `--accent-primary` (neither old name is defined there; the hover colours silently failed).

## Evidence

- Tests (`tests/dashboard-menus.test.ts`, now 8): the time formatter on valid, missing, null, NaN, string and object inputs; the handler no longer overwrites the timestamp; every listed class used by the page has a rule in a loaded stylesheet; every variable the ported block uses is defined by the loaded theme.
- Live, 1024 px, real dashboard after a free local-model run: `p317-dashboard-polish/after-tasks-thoughts-plugins-1024.png`, `after-check.json` (0 "Invalid Date" on the page; thought times like "4:27:34 PM"; thought headers lay out as a flex row). Before: `docs/evidence/p316-local-chat/dashboard-local-1024.png` shows "reasoning Invalid Date" and an unstyled "Attach image" button.

## Not done

- 390 px was not re-screenshotted for these panels.
- The classes were compared by name only. A rule that exists in a loaded sheet for a class could still be wrong for it; the screenshot is the check.
- A goal that needs live data (for example "what PR are we on") run on the local model gets a confident made-up answer. That is a routing gap, not styling, and is not fixed here.

## Four-state table

| Item | State |
|---|---|
| Thought and task timestamps | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (1024 px) |
| Ported component styles | CODE COMPLETE, TEST VERIFIED (rules and variables), LIVE VERIFIED (task card, thought cards, plugin pill at 1024 px) |
| Same panels at 390 px | UNPROVEN |
| Local model refusing live-data goals | NOT BUILT |
