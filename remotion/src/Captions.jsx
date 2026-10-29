import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';
import {anton} from './fonts';

// Group word-level captions into short phrases (break on punctuation or at maxWords)
const buildPhrases = (caps, maxWords = 4) => {
  const phrases = [];
  let cur = [];
  for (let i = 0; i < caps.length; i++) {
    cur.push(caps[i]);
    const w = (caps[i].text || '').trim();
    const endsPunct = /[.,!?;:]$/.test(w);
    if (cur.length >= maxWords || endsPunct) {
      phrases.push({words: cur, startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs});
      cur = [];
    }
  }
  if (cur.length) phrases.push({words: cur, startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs});
  return phrases;
};

export const Captions = ({captions = [], accent = '#F7931A'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ms = (frame / fps) * 1000;
  if (!captions.length) return null;
  const phrases = buildPhrases(captions, 3);
  let idx = -1;
  for (let i = 0; i < phrases.length; i++) {
    if (ms >= phrases[i].startMs) idx = i;
  }
  if (idx === -1) return null;
  const ph = phrases[idx];
  const local = Math.max(0, frame - (ph.startMs / 1000) * fps);
  const pop = spring({frame: local, fps, config: {damping: 16, mass: 0.6}});
  const scale = interpolate(pop, [0, 1], [0.86, 1]);
  return (
    <AbsoluteFill
      style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: '390px', paddingLeft: '90px', paddingRight: '90px'}}
    >
      <div style={{
        fontFamily: anton, fontWeight: 400, fontSize: 86, lineHeight: 1.05,
        textTransform: 'uppercase', textAlign: 'center', letterSpacing: 1,
        textShadow: '0 6px 24px rgba(0,0,0,0.95), 0 2px 4px rgba(0,0,0,0.95)',
        maxWidth: '720px', scale: String(scale),
      }}>
        {ph.words.map((w, i) => {
          const active = ms >= w.startMs && ms < w.endMs;
          return (
            <span key={i} style={{color: active ? accent : 'white'}}>
              {w.text}{i < ph.words.length - 1 ? ' ' : ''}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
