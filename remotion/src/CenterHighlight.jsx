import React from 'react';
import {staticFile, useCurrentFrame, useVideoConfig, spring, interpolate, Img} from 'remotion';

const COIN_NAMES = {
  btc: ['bitcoin', 'btc'], eth: ['ethereum', 'ether', 'eth'], sol: ['solana', 'sol'],
  xrp: ['xrp', 'ripple'], ada: ['cardano', 'ada'], bnb: ['bnb', 'binance'],
  usdt: ['tether', 'usdt'], doge: ['dogecoin', 'doge'],
};

const findWindows = (captions, ticker) => {
  const names = COIN_NAMES[(ticker || '').toLowerCase()];
  if (!names || !captions || !captions.length) return [];
  const wins = [];
  captions.forEach((w) => {
    const t = (w.text || '').toLowerCase().replace(/[^a-z]/g, '');
    if (names.includes(t)) wins.push({start: Math.max(0, w.startMs - 150), end: w.startMs + 1700});
  });
  return wins;
};

export const CenterHighlight = ({captions, ticker}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const wins = findWindows(captions, ticker);
  const active = wins.find((w) => ms >= w.start && ms <= w.end);
  if (!active) return null;
  const localFrames = frame - (active.start / 1000) * fps;
  const winFrames = ((active.end - active.start) / 1000) * fps;
  const inPop = spring({frame: localFrames, fps, config: {damping: 12, mass: 0.8}});
  const fadeOut = interpolate(localFrames, [winFrames - 9, winFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = Math.min(inPop, fadeOut);
  const scale = interpolate(inPop, [0, 1], [0.5, 1]);
  const float = Math.sin((frame / fps) * 2.0) * 8;
  return (
    <div style={{position: 'absolute', top: 400, left: 0, right: 0, height: 760, display: 'flex', justifyContent: 'center', alignItems: 'center'}}>
      <Img src={staticFile('logos/' + (ticker || 'btc') + '.png')} style={{width: 220, height: 220, opacity: opacity, transform: 'translateY(' + float + 'px) scale(' + scale + ')', filter: 'drop-shadow(0 20px 55px rgba(0,0,0,0.6))'}} />
    </div>
  );
};
