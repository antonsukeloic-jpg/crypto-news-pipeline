import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {inter, mono} from './fonts';
import {focusPos} from './focusCrop';

// 5HU Reel / Short cover, 1080x1920 JPEG. The real photo carries it: who / what the story is about,
// a 2-6 word hook, the 5HU mark small in the corner.
// Instagram's profile grid shows only the middle 1080x1440 (y 240-1680), so everything important sits inside that band.
const B = {lime: '#C8FF2E', black: '#0A0A0A', white: '#F5F5F2'};

export const FiveHuCover = ({scenes = [], coverHook, episode}) => {
  const pick = scenes.find((s) => s.real && s.image) || scenes.find((s) => s.image) || {};
  const hook = String(coverHook || (scenes[0] && scenes[0].on_screen_text) || '').trim();
  const words = hook.split(/\s+/).filter(Boolean).slice(0, 6);
  const clean = (w) => String(w || '').replace(/[^\p{L}\d]/gu, '');
  const key = words.reduce((b, w, k) => (clean(w).length > clean(words[b]).length ? k : b), 0);
  const chars = words.join(' ').length;
  const size = chars > 26 ? 104 : chars > 16 ? 128 : 156;
  return (
    <AbsoluteFill style={{backgroundColor: B.black}}>
      {pick.image ? (
        <Img src={staticFile(pick.image)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: focusPos(pick, 1080, 1920, '50% 28%')}} />
      ) : null}
      <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 26%, rgba(0,0,0,0) 46%, rgba(0,0,0,0.88) 84%, rgba(0,0,0,0.95) 100%)'}} />
      <div style={{position: 'absolute', top: 290, left: 80, right: 80, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontFamily: inter, fontWeight: 900, fontSize: 64, letterSpacing: -3, color: B.white, display: 'flex', alignItems: 'baseline',
          textShadow: '0 4px 24px rgba(0,0,0,0.6)'}}>
          5HU<span style={{display: 'inline-block', width: 16, height: 16, borderRadius: 8, background: B.lime, marginLeft: 5}} />
        </div>
        <div style={{fontFamily: mono, fontSize: 24, letterSpacing: 4, color: B.white, opacity: 0.92, textShadow: '0 2px 12px rgba(0,0,0,0.7)'}}>WHO'S NEXT{episode ? ' Nº' + String(episode).padStart(3, '0') : ''}</div>
      </div>
      {words.length ? (
        <div style={{position: 'absolute', left: 80, right: 80, bottom: 330, fontFamily: inter, fontWeight: 900, fontSize: size, lineHeight: 0.96,
          letterSpacing: -4, textTransform: 'uppercase', color: B.white, textShadow: '0 4px 30px rgba(0,0,0,0.7)'}}>
          {words.map((w, k) => (
            <span key={k} style={{display: 'inline-block', marginRight: '0.22em', position: 'relative'}}>
              {k === key && <span style={{position: 'absolute', left: '-0.08em', right: '-0.08em', top: '0.1em', bottom: '0.02em', background: B.lime}} />}
              <span style={{position: 'relative', color: k === key ? B.black : B.white, textShadow: k === key ? 'none' : undefined}}>{w}</span>
            </span>
          ))}
        </div>
      ) : null}
      {pick.credit ? (
        <div style={{position: 'absolute', left: 80, bottom: 268, fontFamily: mono, fontSize: 22, letterSpacing: 3, color: B.white, opacity: 0.7,
          textTransform: 'uppercase'}}>photo · {String(pick.credit).slice(0, 40)}</div>
      ) : null}
    </AbsoluteFill>
  );
};
