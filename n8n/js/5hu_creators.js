// Designer / label accounts for tags + links. Conservative: a handle is kept ONLY if a real profile URL with
// that handle shows up in what Perplexity actually retrieved (search results / citations), never from model memory.
// Fail-safe: any problem -> no creators (posts just go out without tags).
const b = $input.first().json || {};
let reply = '', seen = '';
try {
  for (const o of (b.output || [])) {
    if (!o) continue;
    if (o.type === 'message') {
      for (const c of (o.content || [])) {
        if (c.type === 'output_text') reply += c.text || '';
        seen += ' ' + JSON.stringify(c.annotations || []);
      }
    } else seen += ' ' + JSON.stringify(o);
  }
} catch (e) {}
seen = seen.toLowerCase();
let list = [];
try { const j = JSON.parse(reply.slice(reply.indexOf('{'), reply.lastIndexOf('}') + 1)); list = Array.isArray(j.creators) ? j.creators : []; } catch (e) {}
const handle = (h) => String(h || '').trim().replace(/^@/, '').replace(/^https?:\/\/(www\.)?(instagram|tiktok)\.com\/@?/i, '').replace(/[/?#].*$/, '');
const okH = (h) => /^[A-Za-z0-9._]{2,30}$/.test(h);
const out = [];
for (const c of list.slice(0, 2)) {
  const name = String(c.name || '').trim().slice(0, 60);
  if (!name) continue;
  let ig = handle(c.instagram), tt = handle(c.tiktok), web = '';
  if (!(okH(ig) && seen.includes('instagram.com/' + ig.toLowerCase()))) ig = '';
  if (!(okH(tt) && seen.includes('tiktok.com/@' + tt.toLowerCase()))) tt = '';
  try {
    const host = new URL(String(c.website || '')).hostname.replace(/^www\./, '').toLowerCase();
    if (host && host.includes('.') && seen.includes(host) && !/(instagram|tiktok|facebook|youtube|x\.com|twitter|linktr\.ee|wikipedia|vogue|wwd|hypebeast)/.test(host)) web = 'https://' + host;
  } catch (e) {}
  if (ig || tt || web) out.push({ name, role: String(c.role || '').slice(0, 20), instagram: ig, tiktok: tt, website: web });
}
return [{ json: { creators: out } }];
