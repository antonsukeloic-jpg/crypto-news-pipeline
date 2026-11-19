// Apply the Perplexity fact-check to the script. Fail-safe: any problem -> the original script goes on unchanged.
// Output keeps the Anthropic shape ({content:[{text}]}) so "Code in JavaScript" works as before.
const original = $('Message a model').first().json.content[0].text;
const pass = (note) => [{ json: { content: [{ type: 'text', text: original }], factcheck: note } }];
let reply = '';
try {
  const b = $input.first().json || {};
  for (const o of (b.output || [])) {
    if (o && o.type === 'message') for (const c of (o.content || [])) if (c.type === 'output_text') reply += c.text || '';
  }
} catch (e) { return pass({ status: 'no response' }); }
if (!reply) return pass({ status: 'empty response' });
let fc;
try { fc = JSON.parse(reply.slice(reply.indexOf('{'), reply.lastIndexOf('}') + 1)); } catch (e) { return pass({ status: 'unparseable', reply: reply.slice(0, 300) }); }
const fixes = Array.isArray(fc.fixes) ? fc.fixes.slice(0, 6) : [];
let text = original;
const applied = [], skipped = [];
for (const f of fixes) {
  const wrong = String(f.wrong || ''), right = String(f.right || '');
  if (wrong.length < 2 || !right || wrong === right) { skipped.push(f); continue; }
  const esc = JSON.stringify(wrong).slice(1, -1), rep = JSON.stringify(right).slice(1, -1);
  if (!text.includes(esc)) { skipped.push(f); continue; }
  text = text.split(esc).join(rep);
  applied.push({ wrong, right, why: String(f.why || '').slice(0, 160) });
}
try { JSON.parse(text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1)); } catch (e) { return pass({ status: 'fix broke JSON', applied }); }
return [{ json: { content: [{ type: 'text', text }], factcheck: { status: 'checked', ok: !!fc.ok, applied, skipped: skipped.length } } }];
