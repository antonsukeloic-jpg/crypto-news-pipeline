import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';
import {montserrat} from './fonts';

const ACCENT = '#F7931A';

export const Title = ({text, kicker = 'Crypto News'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!text) return null;
  const enter = spring({frame, fps, config: {damping: 200}});
  const x = interpolate(enter, [0, 1], [-60, 0]);
  const opacity = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'flex-start', paddingTop: 220, paddingLeft: 56}}>
      <div style={{
        display: 'flex', alignItems: 'stretch', borderRadius: 14, overflow: 'hidden',
        maxWidth: 920, boxShadow: '0 12px 44px rgba(0,0,0,0.55)',
        translate: x + 'px 0px', opacity, fontFamily: montserrat,
      }}>
        <div style={{background: ACCENT, color: '#111', fontWeight: 900, fontSize: 26, letterSpacing: 1.5, textTransform: 'uppercase', padding: '0 22px', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap'}}>{kicker}</div>
        <div style={{background: 'rgba(12,14,18,0.92)', color: 'white', fontWeight: 700, fontSize: 38, padding: '16px 26px', lineHeight: 1.12, display: 'flex', alignItems: 'center'}}>{text}</div>
      </div>
    </AbsoluteFill>
  );
};
