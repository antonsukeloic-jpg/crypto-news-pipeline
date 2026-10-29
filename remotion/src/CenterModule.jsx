import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Easing} from 'remotion';
import {montserrat, anton} from './fonts';

const RED = '#ea3943';
const GREEN = '#16c784';

export const CenterModule = ({center}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!center || !center.type || center.type === 'none') return null;

  if (center.type === 'coin') {
    const t = (center.ticker || center.symbol || 'btc').toLowerCase();
    const COIN_NAMES = {btc: 'Bitcoin', eth: 'Ethereum', sol: 'Solana', xrp: 'XRP', ada: 'Cardano', bnb: 'BNB', usdt: 'Tether', doge: 'Dogecoin'};
    const name = center.name || COIN_NAMES[t] || '';
    const logoSrc = center.logo_url ? center.logo_url : staticFile('logos/' + t + '.png');
    const pop = spring({frame, fps, config: {damping: 12, mass: 0.8}});
    const scale = interpolate(pop, [0, 1], [0.5, 1]);
    const float = Math.sin((frame / fps) * 2.0) * 8;
    return (
      <div style={{position: 'absolute', top: 400, left: 0, right: 0, height: 760, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center'}}>
        <Img src={logoSrc} style={{width: 260, height: 260, objectFit: 'contain', opacity: pop, transform: 'translateY(' + float + 'px) scale(' + scale + ')', filter: 'drop-shadow(0 20px 55px rgba(0,0,0,0.6))'}} />
        {name ? <div style={{fontFamily: montserrat, fontWeight: 800, fontSize: 48, color: 'white', marginTop: 26, opacity: pop, textShadow: '0 2px 12px rgba(0,0,0,0.85)'}}>{name}</div> : null}
      </div>
    );
  }

  if (center.type === 'entity' && center.logo_url) {
    const pop = spring({frame, fps, config: {damping: 12, mass: 0.8}});
    const scale = interpolate(pop, [0, 1], [0.6, 1]);
    const float = Math.sin((frame / fps) * 2.0) * 7;
    const isPerson = center.kind === 'person';
    const box = isPerson
      ? {width: 300, height: 300, borderRadius: 300, objectFit: 'cover', border: '6px solid rgba(255,255,255,0.92)'}
      : {width: 330, height: 330, borderRadius: 28, objectFit: 'contain', background: 'white', padding: 30};
    return (
      <div style={{position: 'absolute', top: 400, left: 0, right: 0, height: 760, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center'}}>
        <Img src={center.logo_url} style={{...box, opacity: pop, transform: 'translateY(' + float + 'px) scale(' + scale + ')', boxShadow: '0 20px 55px rgba(0,0,0,0.6)'}} />
        {center.name ? <div style={{fontFamily: montserrat, fontWeight: 800, fontSize: 48, color: 'white', marginTop: 26, opacity: pop, textAlign: 'center', maxWidth: 900, textShadow: '0 2px 12px rgba(0,0,0,0.9)'}}>{center.name}</div> : null}
      </div>
    );
  }

  if (center.type === 'stat') {
    const color = center.color === 'red' ? RED : center.color === 'green' ? GREEN : 'white';
    const target = Number(center.value) || 0;
    const prog = interpolate(frame, [2, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
    const decimals = (String(center.value).split('.')[1] || '').length;
    const cur = (target * prog).toFixed(decimals);
    const numStr = (center.prefix || '') + Number(cur).toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals}) + (center.suffix || '');
    const numOpacity = interpolate(frame, [2, 8], [0, 1], {extrapolateRight: 'clamp'});
    const labelOpacity = interpolate(frame, [18, 30], [0, 1], {extrapolateRight: 'clamp'});
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{background: 'radial-gradient(62% 42% at 50% 40%, rgba(6,8,13,0.6), rgba(6,8,13,0) 72%)'}} />
        <div style={{position: 'absolute', top: 400, left: 0, right: 0, height: 760, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '0 70px'}}>
          <div style={{fontFamily: anton, fontSize: 200, color: color, lineHeight: 0.9, whiteSpace: 'nowrap', opacity: numOpacity, textShadow: '0 10px 55px rgba(0,0,0,0.65)'}}>{numStr}</div>
          {center.label ? <div style={{fontFamily: montserrat, fontWeight: 700, fontSize: 38, color: 'rgba(255,255,255,0.9)', marginTop: 24, opacity: labelOpacity, textAlign: 'center', maxWidth: 880, textShadow: '0 2px 12px rgba(0,0,0,0.85)'}}>{center.label}</div> : null}
        </div>
      </AbsoluteFill>
    );
  }
  return null;
};
