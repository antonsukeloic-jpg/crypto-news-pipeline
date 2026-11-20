import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {inter, mono} from './fonts';
import {focusPos} from './focusCrop';

// 5HU photo carousel, 1080x1350 (4:5) JPEG per frame: frame n = slide n.
// cover (photo + hook) -> 3-4 deeper fact slides -> who's behind it -> save / follow.
// Only the article's real photos are used; a slide without one goes typographic.
// No social handles or platform names on the images: the same slides go to every platform.
const B = {lime: '#C8FF2E', black: '#0A0A0A', white: '#F5F5F2', grey: '#8A8A85'};
const W = 1080, H = 1350, PAD = 84;

export const carouselSlides = (props) => {
  const c = props.carousel || {};
  const facts = (c.slides || []).filter((s) => s && (s.title || s.body)).slice(0, 4);
  const who = (props.creators || []).filter((x) => x && x.name).slice(0, 2);
  const list = [{kind: 'cover'}];
  facts.forEach((f, i) => list.push({kind: 'fact', n: i + 1, title: f.title, body: f.body}));
  if (who.length) list.push({kind: 'who', who});
  list.push({kind: 'end'});
  return list;
};

const Mark = ({color = B.white, size = 44}) => (
  <div style={{fontFamily: inter, fontWeight: 900, fontSize: size, letterSpacing: -2, color, display: 'flex', alignItems: 'baseline', lineHeight: 1}}>
    5HU<span style={{display: 'inline-block', width: size * 0.25, height: size * 0.25, borderRadius: size, background: B.lime, marginLeft: 4}} />
  </div>
);

const Pager = ({i, n, color = B.white}) => (
  <div style={{fontFamily: mono, fontSize: 24, letterSpacing: 3, color, opacity: 0.85}}>{String(i + 1).padStart(2, '0')}/{String(n).padStart(2, '0')}</div>
);

const Hook = ({text, size}) => {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean).slice(0, 6);
  const clean = (w) => String(w || '').replace(/[^\p{L}\d]/gu, '');
  const key = words.reduce((b, w, k) => (clean(w).length > clean(words[b]).length ? k : b), 0);
  return (
    <div style={{fontFamily: inter, fontWeight: 900, fontSize: size, lineHeight: 0.96, letterSpacing: -4, textTransform: 'uppercase', color: B.white}}>
      {words.map((w, k) => (
        <span key={k} style={{display: 'inline-block', marginRight: '0.22em', position: 'relative'}}>
          {k === key && <span style={{position: 'absolute', left: '-0.08em', right: '-0.08em', top: '0.1em', bottom: '0.02em', background: B.lime}} />}
          <span style={{position: 'relative', color: k === key ? B.black : B.white, textShadow: k === key ? 'none' : '0 4px 30px rgba(0,0,0,0.6)'}}>{w}</span>
        </span>
      ))}
    </div>
  );
};

// zoom: slow push-in of the PHOTO only (TikTok slideshow); the frame, text and layout stay still
const Photo = ({p, w = W, h = H, pos = '50% 30%', zoom = 1}) => {
  if (!(p && p.image)) return null;
  const op = focusPos(p, w, h, pos);
  return <Img src={staticFile(p.image)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: op,
    transform: zoom !== 1 ? `scale(${zoom})` : undefined, transformOrigin: op}} />;
};

export const FiveHuCarousel = (props) => {
  const cf = useCurrentFrame();
  const frame = props.slideIndex ?? cf;   // the TikTok slideshow (FiveHuSlideshow) picks the slide itself
  const slides = carouselSlides(props);
  const s = slides[Math.min(frame, slides.length - 1)];
  const n = slides.length;
  const seen = new Set();
  const photos = (props.scenes || []).filter((x) => x.real && x.image && !seen.has(x.image) && seen.add(x.image));
  const c = props.carousel || {};

  if (s.kind === 'cover') {
    const hook = c.cover || (props.scenes && props.scenes[0] && props.scenes[0].on_screen_text) || '';
    const chars = String(hook).length;
    const p = photos[0];
    return (
      <AbsoluteFill style={{backgroundColor: B.black}}>
        <Photo p={p} zoom={props.photoZoom || 1} />
        <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.9) 88%, rgba(0,0,0,0.95) 100%)'}} />
        <div style={{position: 'absolute', top: 72, left: PAD, right: PAD, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <Mark />
          <div style={{fontFamily: mono, fontSize: 24, letterSpacing: 4, color: B.white}}>WHO'S NEXT</div>
        </div>
        <div style={{position: 'absolute', left: PAD, right: PAD, bottom: 150}}>
          <Hook text={hook} size={chars > 26 ? 100 : chars > 16 ? 120 : 148} />
        </div>
        <div style={{position: 'absolute', left: PAD, right: PAD, bottom: 72, display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 22,
          letterSpacing: 3, color: B.white, textTransform: 'uppercase'}}>
          <span style={{opacity: 0.65}}>{p && p.credit ? 'photo · ' + String(p.credit).slice(0, 36) : ''}</span>
          <span>{props.slideIndex == null ? 'swipe →' : ''}</span>
        </div>
      </AbsoluteFill>
    );
  }

  if (s.kind === 'fact') {
    const p = photos[s.n] || null;   // photo 1 is the cover; facts take the next photos, the rest go typographic
    const title = String(s.title || '');
    const body = String(s.body || '');
    if (p) {
      return (
        <AbsoluteFill style={{backgroundColor: B.black}}>
          <div style={{position: 'absolute', top: 0, left: 0, width: W, height: 700, overflow: 'hidden'}}><Photo p={p} w={W} h={700} pos="50% 25%" zoom={props.photoZoom || 1} /></div>
          <div style={{position: 'absolute', top: 0, left: 0, width: W, height: 200, background: 'linear-gradient(to bottom, rgba(0,0,0,0.55), rgba(0,0,0,0))'}} />
          <div style={{position: 'absolute', top: 64, left: PAD, right: PAD, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <Mark size={36} /><Pager i={frame} n={n} />
          </div>
          {p.credit ? <div style={{position: 'absolute', top: 650, right: PAD, fontFamily: mono, fontSize: 18, letterSpacing: 2, color: B.white, opacity: 0.75,
            textTransform: 'uppercase', textShadow: '0 1px 8px rgba(0,0,0,0.8)'}}>photo · {String(p.credit).slice(0, 36)}</div> : null}
          <div style={{position: 'absolute', top: 760, left: PAD, right: PAD}}>
            <div style={{fontFamily: mono, fontSize: 28, color: B.lime, letterSpacing: 3, marginBottom: 22}}>{String(s.n).padStart(2, '0')}</div>
            <div style={{fontFamily: inter, fontWeight: 900, fontSize: title.length > 34 ? 58 : 68, lineHeight: 1, letterSpacing: -2, color: B.white,
              textTransform: 'uppercase', marginBottom: 28}}>{title}</div>
            <div style={{fontFamily: inter, fontWeight: 500, fontSize: body.length > 150 ? 32 : 36, lineHeight: 1.32, color: B.white, opacity: 0.86}}>{body}</div>
          </div>
        </AbsoluteFill>
      );
    }
    return (
      <AbsoluteFill style={{backgroundColor: B.black}}>
        <div style={{position: 'absolute', top: 72, left: PAD, right: PAD, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <Mark size={36} /><Pager i={frame} n={n} />
        </div>
        <div style={{position: 'absolute', top: 150, left: PAD - 10, fontFamily: inter, fontWeight: 900, fontSize: 380, lineHeight: 1, letterSpacing: -20,
          color: B.lime}}>{String(s.n).padStart(2, '0')}</div>
        <div style={{position: 'absolute', bottom: 120, left: PAD, right: PAD}}>
          <div style={{fontFamily: inter, fontWeight: 900, fontSize: title.length > 34 ? 72 : 84, lineHeight: 0.98, letterSpacing: -3, color: B.white,
            textTransform: 'uppercase', marginBottom: 34}}>{title}</div>
          <div style={{fontFamily: inter, fontWeight: 500, fontSize: 38, lineHeight: 1.32, color: B.white, opacity: 0.86}}>{body}</div>
        </div>
      </AbsoluteFill>
    );
  }

  if (s.kind === 'who') {
    const host = (u) => String(u || '').replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '');
    const credits = [...new Set(photos.map((x) => x.credit).filter(Boolean))].slice(0, 4);
    return (
      <AbsoluteFill style={{backgroundColor: B.black}}>
        <div style={{position: 'absolute', top: 72, left: PAD, right: PAD, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <Mark size={36} /><Pager i={frame} n={n} />
        </div>
        <div style={{position: 'absolute', top: 300, left: PAD, right: PAD}}>
          <div style={{fontFamily: mono, fontSize: 28, letterSpacing: 4, color: B.lime, marginBottom: 40}}>WHO'S BEHIND IT</div>
          {s.who.map((x, k) => (
            <div key={k} style={{marginBottom: 56}}>
              <div style={{fontFamily: inter, fontWeight: 900, fontSize: String(x.name).length > 18 ? 84 : 112, lineHeight: 0.95, letterSpacing: -4, color: B.white,
                textTransform: 'uppercase'}}>{x.name}</div>
              {x.website ? <div style={{fontFamily: mono, fontSize: 34, color: B.lime, marginTop: 18}}>{host(x.website)}</div> : null}
            </div>
          ))}
        </div>
        {credits.length ? <div style={{position: 'absolute', bottom: 80, left: PAD, right: PAD, fontFamily: mono, fontSize: 22, letterSpacing: 2, color: B.grey,
          textTransform: 'uppercase'}}>photos · {credits.join(' · ')}</div> : null}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{backgroundColor: B.lime}}>
      <div style={{position: 'absolute', top: 72, left: PAD, right: PAD, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontFamily: mono, fontSize: 24, letterSpacing: 4, color: B.black}}>WHO'S NEXT</div><Pager i={frame} n={n} color={B.black} />
      </div>
      <div style={{position: 'absolute', top: 360, left: PAD, right: PAD, fontFamily: inter, fontWeight: 900, fontSize: 150, lineHeight: 0.92, letterSpacing: -7,
        color: B.black, textTransform: 'uppercase'}}>We find<br />them<br />first.</div>
      <div style={{position: 'absolute', bottom: 110, left: PAD, right: PAD, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end'}}>
        <div style={{fontFamily: inter, fontWeight: 800, fontSize: 40, lineHeight: 1.2, color: B.black}}>Save this.<br />Follow for who's next.</div>
        <div style={{fontFamily: inter, fontWeight: 900, fontSize: 96, letterSpacing: -4, color: B.black, lineHeight: 1}}>5HU</div>
      </div>
    </AbsoluteFill>
  );
};
