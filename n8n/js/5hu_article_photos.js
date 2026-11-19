// Real photos from the article page (designer portrait, looks, campaign). The script assigns them to scenes.
const prev = $input.first().json;
let html = '';
try { const r = $('Article - Fetch').first().json; html = typeof r.data === 'string' ? r.data : (typeof r === 'string' ? r : ''); } catch (e) {}
const link = $('Parse Selection').first().json.link || '';
const abs = (u) => { try { return new URL(u.replace(/&amp;/g, '&'), link).href; } catch (e) { return ''; } };
const attr = (tag, a) => { const m = tag.match(new RegExp('\\s' + a + '\\s*=\\s*["\']([^"\']*)["\']', 'i')); return m ? m[1] : ''; };
const best = (srcset) => {
  let top = '', w = 0;
  for (const part of String(srcset || '').split(',')) {
    const [u, d] = part.trim().split(/\s+/);
    const n = parseFloat(d) || 1;
    if (u && n >= w) { w = n; top = u; }
  }
  return top;
};
const BAD = /(logo|icon|avatar|sprite|placeholder|blank|pixel|spacer|badge|emoji|author|profile|newsletter|banner|advert|\/ads?\/|tracking|gravatar|\.svg|\.gif)/i;
const found = [];
const push = (u, alt, src) => {
  u = abs(u);
  if (!/^https?:/.test(u) || BAD.test(u)) return;
  const key = u.split('?')[0].replace(/[-_](\d{2,4})x(\d{2,4})(?=\.\w+$)/, '');
  if (found.some(f => f.key === key)) return;
  found.push({ key, url: u, alt: String(alt || '').replace(/\s+/g, ' ').trim().slice(0, 140), src });
};
const og = html.match(/<meta[^>]+property=["']og:image["'][^>]*>/i) || html.match(/<meta[^>]+name=["']twitter:image["'][^>]*>/i);
if (og) push(attr(og[0], 'content'), 'lead image', 'og');
// article body images (figure captions win over alt)
const body = (html.match(/<article[\s\S]*<\/article>/i) || [html])[0];
const figs = body.match(/<figure[\s\S]*?<\/figure>/gi) || [];
for (const f of figs) {
  const img = (f.match(/<img[^>]*>/i) || [''])[0];
  if (!img) continue;
  const cap = (f.match(/<figcaption[^>]*>([\s\S]*?)<\/figcaption>/i) || ['', ''])[1].replace(/<[^>]+>/g, ' ');
  push(best(attr(img, 'srcset') || attr(img, 'data-srcset')) || attr(img, 'data-src') || attr(img, 'src'), cap || attr(img, 'alt'), 'figure');
}
for (const img of body.match(/<img[^>]*>/gi) || []) {
  const w = parseInt(attr(img, 'width'), 10);
  if (w && w < 400) continue;
  push(best(attr(img, 'srcset') || attr(img, 'data-srcset')) || attr(img, 'data-src') || attr(img, 'data-lazy-src') || attr(img, 'src'), attr(img, 'alt'), 'img');
}
// the page may be blocked (bot walls): add the photos and full text that came with the RSS item
let feedItem = {};
try { feedItem = (($('Combine Feeds').first().json.candidates) || []).find(c => c.link === link) || {}; } catch (e) {}
for (const im of (feedItem.images || [])) push(im.url, im.alt, 'feed');
let articleText = prev.articleText || '';
if ((!articleText || articleText.length < 300 || /awsWaf|captcha|access denied|just a moment/i.test(articleText)) && feedItem.body && feedItem.body.length > 200) articleText = feedItem.body;
const photos = found.slice(0, 10).map((f, i) => ({ n: i + 1, url: f.url, alt: f.alt }));
const photosText = photos.length
  ? photos.map(p => p.n + '. ' + (p.alt || '(no caption)')).join('\n')
  : '(none - the article has no usable photos)';
return [{ json: Object.assign({}, prev, { articleText, photos, photosText }) }];
