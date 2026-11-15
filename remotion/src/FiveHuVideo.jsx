import React from 'react';
import {AbsoluteFill, Img, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Easing} from 'remotion';
import {serif, inter, mono} from './fonts';
import {buildCaptions, sceneTimeline} from './timing';

// 5HU - "who's next" fashion look: editorial serif, flash cuts, grain, pink accents.
const PINK = '#FF3D9A';
const OUTRO_SEC = 1.7;
const MUSIC_VOL = 0.42;   // techno bed under the voice (louder on the outro)

const Grain = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{mixBlendMode: 'overlay', opacity: 0.22, pointerEvents: 'none'}}>
      <svg width="1080" height="1920">
        <filter id={'g' + (frame % 8)}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={frame % 8} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={'url(#g' + (frame % 8) + ')'} />
      </svg>
    </AbsoluteFill>
  );
};

// techno-clip motion: kick pulse on every beat, hard re-frame every bar, glitch on scene cuts
const BPM = 132;
const FRAMINGS = [
  {z: 1.0, x: 0, y: 0}, {z: 1.32, x: -60, y: -40}, {z: 1.16, x: 50, y: 60}, {z: 1.45, x: 30, y: -90},
];
const Media = ({scene, dur, i, from}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const beat = (fps * 60) / BPM;
  const abs = from + frame;
  const sinceKick = abs % beat;
  const kick = interpolate(sinceKick, [0, 5], [1.045, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.quad)});
  // hard re-frame every bar (4 beats) inside the scene
  const bar = Math.floor(frame / (beat * 4));
  const fr = FRAMINGS[(bar + i) % FRAMINGS.length];
  const punch = interpolate(frame, [0, 7], [1.12, 1.0], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const drift = interpolate(frame, [0, dur], [1, 1.05]);
  // glitch on the cut: jitter + RGB-ish ghost for 6 frames
  const glitch = frame < 6;
  const jx = glitch ? ((frame * 37) % 7 - 3) * 14 : 0;
  const base = {position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
    scale: String(fr.z * punch * drift * kick), translate: (fr.x + jx) + 'px ' + fr.y + 'px',
    filter: 'contrast(1.14) saturate(0.88) brightness(0.95)'};
  const src = scene.video ? null : staticFile(scene.image);
  return (
    <AbsoluteFill>
      {scene.video
        ? <OffthreadVideo src={staticFile(scene.video)} muted style={base} />
        : <Img src={src} style={base} />}
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
  if (frame < bar) return null;
  return <AbsoluteFill style={{background: 'white', opacity: interpolate(t, [0, 3], [0.35, 0], {extrapolateRight: 'clamp'})}} />;
};

const Flash = () => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, 1, 6], [0.95, 0.85, 0], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: 'white', opacity: o}} />;
};

const Grade = () => (
  <>
    <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.62) 0%, rgba(0,0,0,0) 34%, rgba(0,0,0,0) 58%, rgba(0,0,0,0.7) 100%)'}} />
    <AbsoluteFill style={{background: 'radial-gradient(120% 80% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)'}} />
  </>
);

const Headline = ({text}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!text) return null;
  const words = String(text).split(/\s+/).filter(Boolean);
  return (
    <div style={{position: 'absolute', top: 250, left: 72, right: 110, fontFamily: serif, fontStyle: 'italic', fontSize: 132,
      lineHeight: 0.98, letterSpacing: -2, color: 'white', textShadow: '0 6px 40px rgba(0,0,0,0.45)'}}>
      {words.map((w, i) => {
        const p = spring({frame: frame - 4 - i * 3, fps, config: {damping: 18, mass: 0.7}});
        return (
          <span key={i} style={{display: 'inline-block', overflow: 'hidden', verticalAlign: 'top', paddingBottom: 14, marginRight: 26}}>
            <span style={{display: 'inline-block', translate: '0px ' + interpolate(p, [0, 1], [110, 0]) + '%'}}>{w}</span>
          </span>
        );
      })}
    </div>
  );
};

const Header = ({stamp}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const prog = frame / Math.max(1, durationInFrames - 1);
  return (
    <>
      <div style={{position: 'absolute', top: 110, left: 72, right: 72, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontFamily: inter, fontWeight: 900, fontSize: 58, letterSpacing: -3, color: 'white', display: 'flex', alignItems: 'baseline'}}>
          5HU<span style={{color: PINK, marginLeft: 2}}>.</span>
        </div>
        <div style={{fontFamily: mono, fontSize: 24, letterSpacing: 3, color: 'white', opacity: 0.9}}>WHO'S NEXT · {stamp}</div>
      </div>
      <div style={{position: 'absolute', top: 196, left: 72, right: 72, height: 3, background: 'rgba(255,255,255,0.25)'}}>
        <div style={{width: (prog * 100) + '%', height: '100%', background: PINK}} />
      </div>
      <div style={{position: 'absolute', top: 960, right: -168, rotate: '90deg', fontFamily: mono, fontSize: 21, letterSpacing: 6, color: 'white', opacity: 0.7, whiteSpace: 'nowrap'}}>
        WE FIND THEM FIRST — 5HU — WE FIND THEM FIRST
      </div>
    </>
  );
};

const Center = ({center}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!center || !center.type || center.type === 'none') return null;
  const p = spring({frame: frame - 6, fps, config: {damping: 14, mass: 0.8}});
  if (center.type === 'entity' && center.logo_url) {
    const isPerson = center.kind === 'person';
    return (
      <div style={{position: 'absolute', top: 640, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
        <div style={{background: '#f6f3ee', padding: '20px 20px 0 20px', boxShadow: '0 30px 70px rgba(0,0,0,0.55)',
          rotate: interpolate(p, [0, 1], [-14, -4]) + 'deg', scale: String(interpolate(p, [0, 1], [0.7, 1])), opacity: p}}>
          <Img src={center.logo_url} style={{width: 380, height: isPerson ? 440 : 300, objectFit: isPerson ? 'cover' : 'contain', background: 'white', display: 'block'}} />
          <div style={{fontFamily: mono, fontSize: 26, letterSpacing: 2, color: '#111', textTransform: 'uppercase', padding: '20px 4px 24px', maxWidth: 380}}>
            {center.name || ''}
          </div>
        </div>
      </div>
    );
  }
  if (center.type === 'stat') {
    const target = Number(center.value) || 0;
    const prog = interpolate(frame, [4, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
    const decimals = (String(center.value).split('.')[1] || '').length;
    const num = (center.prefix || '') + Number((target * prog).toFixed(decimals)).toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals}) + (center.suffix || '');
    return (
      <div style={{position: 'absolute', top: 700, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: p}}>
        <div style={{fontFamily: serif, fontSize: 300, lineHeight: 0.85, color: PINK, letterSpacing: -6, textShadow: '0 12px 60px rgba(0,0,0,0.5)'}}>{num}</div>
        {center.label ? <div style={{fontFamily: mono, fontSize: 28, letterSpacing: 3, color: 'white', textTransform: 'uppercase', marginTop: 18, textAlign: 'center', maxWidth: 860}}>{center.label}</div> : null}
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
  const local = frame - (ph[0].startMs / 1000) * fps;
  const pop = spring({frame: local, fps, config: {damping: 20, mass: 0.5}});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 360, paddingLeft: 80, paddingRight: 80}}>
      <div style={{fontFamily: inter, fontWeight: 800, fontSize: 64, lineHeight: 1.25, letterSpacing: -1, color: 'white', textAlign: 'center',
        textShadow: '0 4px 22px rgba(0,0,0,0.8)', translate: '0px ' + interpolate(pop, [0, 1], [18, 0]) + 'px', opacity: pop}}>
        {ph.map((w, i) => {
          const on = ms >= w.startMs && ms < w.endMs + 60;
          return (
            <span key={i} style={{display: 'inline-block', margin: '0 6px', padding: '0 12px', borderRadius: 12,
              background: on ? PINK : 'transparent', color: on ? '#0b0b0b' : 'white', textShadow: on ? 'none' : undefined}}>
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
  const bg = interpolate(frame, [0, 8], [0, 0.88], {extrapolateRight: 'clamp'});
  const p = spring({frame: frame - 3, fps, config: {damping: 16}});
  const q = spring({frame: frame - 10, fps, config: {damping: 18}});
  return (
    <AbsoluteFill style={{background: 'rgba(8,8,8,' + bg + ')', justifyContent: 'center', alignItems: 'center'}}>
      <div style={{fontFamily: inter, fontWeight: 900, fontSize: 300, letterSpacing: -16, color: 'white', lineHeight: 0.9, scale: String(interpolate(p, [0, 1], [1.25, 1])), opacity: p}}>
        5HU<span style={{color: PINK}}>.</span>
      </div>
      <div style={{fontFamily: serif, fontStyle: 'italic', fontSize: 84, color: PINK, marginTop: 10, opacity: q, translate: '0px ' + interpolate(q, [0, 1], [30, 0]) + 'px'}}>we find them first.</div>
      <div style={{fontFamily: mono, fontSize: 26, letterSpacing: 5, color: 'white', marginTop: 40, opacity: q}}>FOLLOW FOR THE NEXT BIG NAME</div>
    </AbsoluteFill>
  );
};

const stampFrom = (voice) => {
  const m = String(voice || '').match(/(\d{13})/);
  const d = m ? new Date(Number(m[1])) : new Date();
  const p = (n) => String(n).padStart(2, '0');
  return p(d.getUTCDate()) + '.' + p(d.getUTCMonth() + 1) + '.' + String(d.getUTCFullYear()).slice(2);
};

export const FiveHuVideo = ({scenes = [], voice, captions, voiceover, fps}) => {
  const {durationInFrames} = useVideoConfig();
  const f = fps || 30;
  const caps = (captions && captions.length) ? captions : buildCaptions(voiceover, durationInFrames, f);
  const tl = sceneTimeline(scenes, caps, durationInFrames, f);
  const outroFrom = Math.max(0, durationInFrames - Math.round(OUTRO_SEC * f));
  const subsCaps = caps.filter((c) => (c.startMs / 1000) * f < outroFrom);
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {scenes.map((s, i) => (
        <Sequence key={i} from={tl[i].from} durationInFrames={tl[i].dur}>
          <Media scene={s} dur={tl[i].dur} i={i} from={tl[i].from} />
          <BarFlash from={tl[i].from} />
          <Grade />
          <Center center={s.center} />
          <Headline text={s.on_screen_text} />
          {i > 0 && <Sequence durationInFrames={8}><Flash /></Sequence>}
        </Sequence>
      ))}
      <Grain />
      <Header stamp={stampFrom(voice)} />
      <Sequence durationInFrames={outroFrom}><Subs caps={subsCaps} /></Sequence>
      <Sequence from={outroFrom}><Outro /></Sequence>
      <Audio src={staticFile(voice)} />
      <Audio src={staticFile('music/5hu_techno.mp3')} loop
        volume={(fr) => interpolate(fr, [0, 12, durationInFrames - 20, durationInFrames - 1], [0, MUSIC_VOL, 0.75, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
    </AbsoluteFill>
  );
};
