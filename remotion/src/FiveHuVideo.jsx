import React from 'react';
import {AbsoluteFill, Img, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Easing} from 'remotion';
import {serif, inter, mono} from './fonts';
import {buildCaptions, sceneTimeline} from './timing';

// 5HU brand system. Constant: logo + lime dot, lime/pink/cyan on black & white, lime dot impact on every cut,
// RGB-split outro. Varies per video (seeded): headline layout, transition order, second accent.
const BRAND = {lime: '#C8FF2E', pink: '#FF3D9A', cyan: '#2EE6FF', black: '#0A0A0A', white: '#F5F5F2'};
const OUTRO_SEC = 1.8;
const MUSIC_VOL = 0.6;   // ducks to 0.16 while a word is spoken, swells in pauses

const seedOf = (voice) => { const m = String(voice || '').match(/(\d{13})/); return m ? Number(m[1].slice(-6)) : 7; };

const Grain = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: 0.28, pointerEvents: 'none'}}>
      <Img src={staticFile('fx/grain_' + (frame % 6) + '.png')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    </AbsoluteFill>
  );
};

// techno-clip motion: kick pulse on every beat, hard re-frame every bar, glitch on scene cuts
let BPM = 132;   // set per video from the job (music tempo)
// organic groove: each beat gets its own strength (seeded, repeatable), so the pulse breathes instead of ticking
const rnd = (n) => { const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };
const beatAmp = (b) => { const r = rnd(b); return b % 8 === 0 ? 1.4 : r < 0.3 ? 0 : r < 0.6 ? 0.45 : r < 0.85 ? 1 : 1.6; };
const FRAMINGS = [
  {z: 1.0, x: 0, y: 0}, {z: 1.32, x: -60, y: -40}, {z: 1.16, x: 50, y: 60}, {z: 1.45, x: 30, y: -90},
];
const Media = ({scene, dur, i, from}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const beat = (fps * 60) / BPM;
  const abs = from + frame;
  const sinceKick = abs % beat;
  const amp = beatAmp(Math.floor(abs / beat));
  const kick = 1 + 0.045 * amp * interpolate(sinceKick, [0, 5], [1, 0], {extrapolateRight: 'clamp', easing: Easing.out(Easing.quad)});
  // hard re-frame every bar (4 beats) inside the scene
  const bar = Math.floor(frame / (beat * 4));
  const f0 = FRAMINGS[(bar + i) % FRAMINGS.length];
  // real photos: keep the designer / the pieces in frame (softer zoom); wide shots sit on a blurred copy instead of being cropped
  const fr = scene.real ? {z: 1 + (f0.z - 1) * 0.45, x: f0.x * 0.4, y: f0.y * 0.4} : f0;
  const wide = scene.real && Number(scene.aspect) > 0.68;
  const punch = interpolate(frame, [0, 7], [1.12, 1.0], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const drift = interpolate(frame, [0, dur], [1, 1.05]);
  // glitch on the cut: jitter + RGB-ish ghost for 6 frames
  const glitch = frame < 6;
  const jx = glitch ? ((frame * 37) % 7 - 3) * 14 : 0;
  const base = {position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
    scale: String(fr.z * punch * drift * kick), translate: (fr.x + jx) + 'px ' + fr.y + 'px',
    filter: 'contrast(1.14) saturate(0.88) brightness(0.95)'};
  if (wide) {
    // landscape photo: fill the frame and pan across it (Ken Burns), direction alternates per scene
    const pan = interpolate(frame, [0, dur], i % 2 ? [82, 18] : [18, 82], {extrapolateRight: 'clamp', easing: Easing.inOut(Easing.sin)});
    base.objectPosition = pan + '% 50%';
    base.scale = String(punch * kick * interpolate(frame, [0, dur], [1.04, 1.12]));
    base.translate = jx + 'px 0px';
  }
  const src = scene.video ? null : staticFile(scene.image);
  return (
    <AbsoluteFill>
      {scene.video
        ? <OffthreadVideo src={staticFile(scene.video)} muted style={base} />
        : <Img src={src} style={base} />}
      {scene.credit && <div style={{position: 'absolute', left: 72, top: 262, fontFamily: mono, fontSize: 20, letterSpacing: 3,
        color: BRAND.white, opacity: 0.75, textTransform: 'uppercase', textShadow: '0 2px 8px rgba(0,0,0,0.8)'}}>photo · {scene.credit}</div>}
      {glitch && src && <Img src={src} style={{...base, translate: (fr.x + jx + 22) + 'px ' + fr.y + 'px', mixBlendMode: 'screen', opacity: 0.55,
        filter: 'hue-rotate(300deg) saturate(3)'}} />}
      {glitch && src && <Img src={src} style={{...base, translate: (fr.x + jx - 22) + 'px ' + fr.y + 'px', mixBlendMode: 'screen', opacity: 0.45,
        filter: 'hue-rotate(160deg) saturate(3)'}} />}
    </AbsoluteFill>
  );
};

// tiny strobe on every bar change inside a scene
const BarFlash = ({from}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const bar = (fps * 60 / BPM) * 4;
  const t = frame % bar;
  if (frame < bar || rnd(Math.floor((from + frame) / bar) + 7) < 0.6) return null;
  return <AbsoluteFill style={{background: 'white', opacity: interpolate(t, [0, 3], [0.35, 0], {extrapolateRight: 'clamp'})}} />;
};


// ---- impact transitions (first ~10 frames of every scene after the first)
const shakeOf = (frame, kind) => {
  if (frame > 9) return '0px 0px';
  const a = interpolate(frame, [0, 9], [kind === 'smash' ? 34 : 14, 0], {extrapolateRight: 'clamp'});
  return ((frame * 53) % 3 - 1) * a + 'px ' + ((frame * 31) % 3 - 1) * a + 'px';
};

const Impact = ({kind, accent}) => {
  const frame = useCurrentFrame();
  const ring = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const dot = (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <div style={{width: 60 + ring * 1500, height: 60 + ring * 1500, borderRadius: '50%', border: (28 * (1 - ring) + 2) + 'px solid ' + BRAND.lime, opacity: 1 - ring}} />
    </AbsoluteFill>
  );
  if (kind === 'wipe') {
    const x = interpolate(frame, [0, 8], [-10, 110], {extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
    return (<>
      <div style={{position: 'absolute', top: 0, bottom: 0, left: (x - 30) + '%', width: '30%', background: BRAND.lime}} />
      <div style={{position: 'absolute', top: 0, bottom: 0, left: (x - 42) + '%', width: '12%', background: accent}} />
      {dot}
    </>);
  }
  if (kind === 'split') {
    if (frame > 7) return dot;
    const bars = [0.18, 0.47, 0.71];
    return (<>
      {bars.map((y, k) => (
        <div key={k} style={{position: 'absolute', left: 0, right: 0, top: (y * 100) + '%', height: 70 + k * 30,
          background: k % 2 ? BRAND.cyan : BRAND.pink, mixBlendMode: 'screen', opacity: 0.75,
          translate: (((frame + k) * 97) % 200 - 100) + 'px 0px'}} />
      ))}
      {dot}
    </>);
  }
  // smash: white flash + shake (shake applied to the scene) + dot
  const o = interpolate(frame, [0, 2, 6], [1, 0.8, 0], {extrapolateRight: 'clamp'});
  return (<><AbsoluteFill style={{background: BRAND.white, opacity: o}} />{dot}</>);
};

const Grade = () => (
  <>
    <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.62) 0%, rgba(0,0,0,0) 34%, rgba(0,0,0,0) 56%, rgba(0,0,0,0.72) 100%)'}} />
    <AbsoluteFill style={{background: 'radial-gradient(120% 80% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)'}} />
  </>
);

// ---- kinetic typography: words slam in (scale + blur), the key word gets a lime block, everything pumps on the kick
const Headline = ({text, layout, accent, from}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!text) return null;
  const words = String(text).split(/\s+/).filter(Boolean);
  const key = words.reduce((b, w, k) => (w.replace(/[^\p{L}\d]/gu, '').length > words[b].replace(/[^\p{L}\d]/gu, '').length ? k : b), 0);
  const beat = (fps * 60) / BPM;
  const pump = 1 + 0.03 * beatAmp(Math.floor((from + frame) / beat)) * interpolate((from + frame) % beat, [0, 5], [1, 0], {extrapolateRight: 'clamp'});
  const L = [
    {top: 300, left: 72, right: 200, font: serif, style: 'italic', size: 138, weight: 400, upper: false, align: 'left'},
    {top: 600, left: 60, right: 180, font: inter, style: 'normal', size: 128, weight: 900, upper: true, align: 'center'},
    {top: 860, left: 72, right: 200, font: inter, style: 'normal', size: 112, weight: 900, upper: true, align: 'left'},
  ][layout];
  return (
    <div style={{position: 'absolute', top: L.top, left: L.left, right: L.right, textAlign: L.align, fontFamily: L.font, fontStyle: L.style,
      fontWeight: L.weight, fontSize: L.size, lineHeight: 0.95, letterSpacing: L.upper ? -4 : -2, color: BRAND.white,
      textTransform: L.upper ? 'uppercase' : 'none', textShadow: '0 2px 2px rgba(0,0,0,0.55), 0 6px 26px rgba(0,0,0,0.75), 0 0 60px rgba(0,0,0,0.5)', scale: String(pump)}}>
      {words.map((w, k) => {
        const p = spring({frame: frame - 3 - k * 3, fps, config: {damping: 13, mass: 0.6, stiffness: 180}});
        const isKey = k === key;
        const fill = interpolate(frame - 6 - k * 3, [0, 6], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <span key={k} style={{display: 'inline-block', marginRight: '0.22em', position: 'relative',
            scale: String(interpolate(p, [0, 1], [2.1, 1])), opacity: Math.min(1, p * 1.4),
            filter: 'blur(' + interpolate(p, [0, 1], [14, 0]) + 'px)', rotate: interpolate(p, [0, 1], [k % 2 ? 6 : -6, 0]) + 'deg'}}>
            {isKey && <span style={{position: 'absolute', left: '-0.08em', right: '-0.08em', top: '0.1em', bottom: '0.02em',
              background: BRAND.lime, clipPath: 'inset(0 ' + (100 - fill) + '% 0 0)', zIndex: 0}} />}
            <span style={{position: 'relative', zIndex: 1, color: isKey ? BRAND.black : BRAND.white, textShadow: isKey ? 'none' : undefined}}>{w}</span>
          </span>
        );
      })}
    </div>
  );
};

const Header = ({stamp, accent}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  const prog = frame / Math.max(1, durationInFrames - 1);
  const intro = spring({frame, fps, config: {damping: 16}});
  return (
    <>
      <div style={{position: 'absolute', top: 150, left: 72, right: 72, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        translate: '0px ' + interpolate(intro, [0, 1], [-60, 0]) + 'px', opacity: intro}}>
        <div style={{fontFamily: inter, fontWeight: 900, fontSize: 60, letterSpacing: -3, color: BRAND.white, display: 'flex', alignItems: 'baseline'}}>
          5HU<span style={{display: 'inline-block', width: 16, height: 16, borderRadius: 8, background: BRAND.lime, marginLeft: 5}} />
        </div>
        <div style={{fontFamily: mono, fontSize: 24, letterSpacing: 3, color: BRAND.white, opacity: 0.9}}>
          WHO'S NEXT <span style={{color: accent}}>●</span> {stamp}
        </div>
      </div>
      <div style={{position: 'absolute', top: 236, left: 72, right: 72, height: 4, background: 'rgba(255,255,255,0.22)'}}>
        <div style={{width: (prog * 100) + '%', height: '100%', background: BRAND.lime}} />
      </div>
      <div style={{position: 'absolute', top: 960, left: -380, rotate: '-90deg', fontFamily: mono, fontSize: 21, letterSpacing: 6, color: accent, opacity: 0.85, whiteSpace: 'nowrap'}}>
        WE FIND THEM FIRST — 5HU — WE FIND THEM FIRST
      </div>
    </>
  );
};

const Center = ({center, accent, compact}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!center || !center.type || center.type === 'none') return null;
  const p = spring({frame: frame - 6, fps, config: {damping: 12, mass: 0.8}});
  if (center.type === 'entity' && (center.logo_url || center.name)) {
    const isPerson = center.kind === 'person' && center.logo_url;
    return (
      <div style={compact ? {position: 'absolute', top: 310, left: 72, scale: '0.52', transformOrigin: 'top left'} : {position: 'absolute', top: 760, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
        <div style={{position: 'relative', background: BRAND.white, padding: '20px 20px 0 20px', boxShadow: '0 30px 70px rgba(0,0,0,0.55)',
          rotate: interpolate(p, [0, 1], [-16, -4]) + 'deg', scale: String(interpolate(p, [0, 1], [0.6, 1])), opacity: p}}>
          <div style={{position: 'absolute', top: -18, left: 120, width: 150, height: 38, background: BRAND.lime, opacity: 0.9, rotate: '3deg'}} />
          {center.logo_url
            ? <Img src={center.logo_url} style={{width: 380, height: isPerson ? 440 : 300, objectFit: isPerson ? 'cover' : 'contain', background: 'white', display: 'block'}} />
            : <div style={{width: 380, height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', background: BRAND.black, color: BRAND.white,
                fontFamily: serif, fontStyle: 'italic', fontSize: String(center.name).length > 12 ? 58 : 84, lineHeight: 0.95, textAlign: 'center', padding: 20}}>{center.name}</div>}
          <div style={{fontFamily: mono, fontSize: 26, letterSpacing: 2, color: BRAND.black, textTransform: 'uppercase', padding: '20px 4px 24px', maxWidth: 380}}>
            {center.name || ''} <span style={{color: accent}}>●</span>
          </div>
        </div>
      </div>
    );
  }
  if (center.type === 'stat') {
    const target = Number(center.value) || 0;
    const prog = interpolate(frame, [4, 26], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
    const decimals = (String(center.value).split('.')[1] || '').length;
    const num = (center.prefix || '') + Number((target * prog).toFixed(decimals)).toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals}) + (center.suffix || '');
    return (
      <div style={{position: 'absolute', top: 700, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: p,
        scale: String(interpolate(p, [0, 1], [1.6, 1]))}}>
        <div style={{fontFamily: inter, fontWeight: 900, fontSize: Math.min(280, Math.round(1500 / Math.max(3, String(num).length))), lineHeight: 0.85, color: BRAND.lime, letterSpacing: -8, whiteSpace: 'nowrap', textShadow: '8px 0 0 ' + accent + ', 0 12px 60px rgba(0,0,0,0.5)'}}>{num}</div>
        {center.label ? <div style={{fontFamily: mono, fontSize: 28, letterSpacing: 3, color: BRAND.white, textTransform: 'uppercase', marginTop: 18, textAlign: 'center', maxWidth: 860}}>{center.label}</div> : null}
      </div>
    );
  }
  return null;
};

const phrasesOf = (caps, max = 4) => {
  const out = []; let cur = [];
  caps.forEach((c) => {
    cur.push(c);
    if (cur.length >= max || /[.,!?;:—–]$/.test((c.text || '').trim())) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  return out;
};

const Subs = ({caps}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const phrases = phrasesOf(caps);
  let ph = null;
  for (const p of phrases) if (ms >= p[0].startMs) ph = p;
  if (!ph) return null;
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 540, paddingLeft: 80, paddingRight: 200}}>
      <div style={{fontFamily: inter, fontWeight: 800, fontSize: 62, lineHeight: 1.3, letterSpacing: -1, color: BRAND.white, textAlign: 'center',
        textShadow: '0 4px 22px rgba(0,0,0,0.85)'}}>
        {ph.map((w, k) => {
          const st = (w.startMs / 1000) * fps;
          const p = spring({frame: frame - st, fps, config: {damping: 14, mass: 0.5}});
          const on = ms >= w.startMs && ms < w.endMs + 60;
          const shown = ms >= w.startMs - 40;
          return (
            <span key={k} style={{display: 'inline-block', margin: '0 6px', padding: '0 12px', borderRadius: 10,
              background: on ? BRAND.lime : 'transparent', color: on ? BRAND.black : BRAND.white, textShadow: on ? 'none' : undefined,
              opacity: shown ? 1 : 0.35, scale: String(on ? interpolate(p, [0, 1], [1.25, 1.08]) : 1)}}>
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Outro = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const bg = interpolate(frame, [0, 5], [0, 1], {extrapolateRight: 'clamp'});
  const p = spring({frame: frame - 2, fps, config: {damping: 14}});
  const q = spring({frame: frame - 10, fps, config: {damping: 18}});
  const split = interpolate(frame, [0, 14], [26, 0], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const logo = (color, dx, extra) => (
    <div style={{position: 'absolute', fontFamily: inter, fontWeight: 900, fontSize: 300, letterSpacing: -16, color, lineHeight: 0.9,
      translate: dx + 'px 0px', ...extra}}>5HU</div>
  );
  return (
    <AbsoluteFill style={{background: 'rgba(10,10,10,' + bg + ')', justifyContent: 'center', alignItems: 'center'}}>
      <div style={{position: 'relative', width: 640, height: 280, display: 'flex', justifyContent: 'center', scale: String(interpolate(p, [0, 1], [1.4, 1])), opacity: p}}>
        {logo(BRAND.pink, -split, {mixBlendMode: 'screen', opacity: 0.9})}
        {logo(BRAND.cyan, split, {mixBlendMode: 'screen', opacity: 0.9})}
        {logo(BRAND.white, 0, {})}
        <div style={{position: 'absolute', right: 2, bottom: 26, width: 52, height: 52, borderRadius: 26, background: BRAND.lime,
          scale: String(spring({frame: frame - 8, fps, config: {damping: 9}}))}} />
      </div>
      <div style={{fontFamily: serif, fontStyle: 'italic', fontSize: 84, color: BRAND.lime, marginTop: 16, opacity: q, translate: '0px ' + interpolate(q, [0, 1], [30, 0]) + 'px'}}>we find them first.</div>
      <div style={{fontFamily: mono, fontSize: 26, letterSpacing: 5, color: BRAND.white, marginTop: 40, opacity: q}}>FOLLOW FOR THE NEXT BIG NAME</div>
    </AbsoluteFill>
  );
};

const stampFrom = (voice) => {
  const m = String(voice || '').match(/(\d{13})/);
  const d = m ? new Date(Number(m[1])) : new Date();
  const p = (n) => String(n).padStart(2, '0');
  return p(d.getUTCDate()) + '.' + p(d.getUTCMonth() + 1) + '.' + String(d.getUTCFullYear()).slice(2);
};

const KINDS = ['wipe', 'split', 'smash'];

const Scene = ({s, i, from, dur, layout, kind, accent}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{translate: i > 0 ? shakeOf(frame, kind) : '0px 0px'}}>
      <Media scene={s} dur={dur} i={i} from={from} />
      <BarFlash from={from} />
      <Grade />
      <Center center={s.center} accent={accent} compact={!!s.real} />
      <Headline text={s.on_screen_text} layout={layout} accent={accent} from={from} />
      {i > 0 && <Sequence durationInFrames={14}><Impact kind={kind} accent={accent} /></Sequence>}
    </AbsoluteFill>
  );
};

export const FiveHuVideo = ({scenes = [], voice, captions, voiceover, fps, music, bpm, signoff, signoffSec}) => {
  BPM = Number(bpm) || 132;
  const {durationInFrames} = useVideoConfig();
  const f = fps || 30;
  const seed = seedOf(voice);
  const accent = seed % 2 ? BRAND.pink : BRAND.cyan;
  const caps = (captions && captions.length) ? captions : buildCaptions(voiceover, durationInFrames, f);
  const tl = sceneTimeline(scenes, caps, durationInFrames, f);
  let outroFrom = Math.max(0, durationInFrames - Math.round(OUTRO_SEC * f));
  const soFrames = signoff ? Math.round((Number(signoffSec) || 2.6) * f) : 0;
  if (signoff) outroFrom = Math.max(0, durationInFrames - soFrames - Math.round(0.6 * f));
  for (let k = caps.length - 1; k > 0; k--) {
    if (/^5HU/i.test(caps[k].text) && /^follow/i.test(caps[k - 1].text)) { outroFrom = Math.max(0, Math.round((caps[k - 1].startMs / 1000) * f) - 6); break; }
  }
  const subsCaps = caps.filter((c) => (c.startMs / 1000) * f < outroFrom);
  return (
    <AbsoluteFill style={{backgroundColor: BRAND.black}}>
      {scenes.map((s, i) => (
        <Sequence key={i} from={tl[i].from} durationInFrames={tl[i].dur}>
          <Scene s={s} i={i} from={tl[i].from} dur={tl[i].dur} accent={accent}
            layout={s.center && s.center.type && s.center.type !== 'none' && !(s.real && s.center.type === 'entity') ? 0 : (s.real && s.center && s.center.type === 'entity') ? 1 + (seed + i) % 2 : (seed + i) % 3} kind={KINDS[(seed + i) % KINDS.length]} />
        </Sequence>
      ))}
      <Grain />
      <Header stamp={stampFrom(voice)} accent={accent} />
      <Sequence durationInFrames={outroFrom}><Subs caps={subsCaps} /></Sequence>
      <Sequence from={outroFrom}><Outro /></Sequence>
      <Audio src={staticFile(voice)} />
      {signoff && <Sequence from={outroFrom + 5}><Audio src={staticFile(signoff)} volume={1.15} /></Sequence>}
      <Audio src={staticFile(music || 'music/5hu_techno.mp3')} loop volume={(fr) => {
        const ms = (fr / f) * 1000;
        const speaking = caps.some((c) => ms >= c.startMs - 80 && ms <= c.endMs + 120);
        const bed = speaking ? 0.36 : MUSIC_VOL;
        const env = interpolate(fr, [0, 12, durationInFrames - 20, durationInFrames - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (fr >= outroFrom ? (signoff ? 0.42 : 0.55) : bed) * env;
      }} />
    </AbsoluteFill>
  );
};
