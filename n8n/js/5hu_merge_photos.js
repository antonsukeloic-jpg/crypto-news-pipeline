// Article/RSS photos first (they are the story's own), then Perplexity image_search results (designer portrait, looks, logo).
const art = $('Article Photos').first().json;
let body = {};
try { body = $input.first().json || {}; } catch (e) {}
const web = [].concat(...((body.output || []).filter(o => o && o.type === 'image_search_results').map(o => o.results || [])));
const out = (art.photos || []).map(p => ({ url: p.url, alt: p.alt || '', from: 'article' }));
const key = (u) => String(u || '').split('?')[0].replace(/\/(w_|h_|c_)[^/]*\//g, '/');
for (const r of web) {
  const u = r.image_url;
  if (!/^https?:\/\//.test(u || '')) continue;
  if ((r.width && r.width < 500) || (r.height && r.height < 500)) continue;
  if (out.some(p => key(p.url) === key(u))) continue;
  const site = (() => { try { return new URL(r.origin_url || u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } })();
  out.push({ url: u, alt: (r.title || '').slice(0, 120) + (site ? ' [' + site + ']' : ''), from: 'web', w: r.width, h: r.height });
}
const photos = out.slice(0, 16).map((p, i) => Object.assign({ n: i + 1 }, p));
const photosText = photos.length
  ? photos.map(p => p.n + '. ' + (p.alt || '(no caption)') + (p.w ? ' (' + p.w + 'x' + p.h + ')' : '')).join('\n')
  : '(none - no usable photos found)';
return [{ json: Object.assign({}, art, { photos, photosText, webPhotos: web.length }) }];
