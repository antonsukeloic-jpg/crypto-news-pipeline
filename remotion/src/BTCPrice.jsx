import React from 'react';
import {staticFile, useCurrentFrame, useVideoConfig, spring, interpolate, Img} from 'remotion';
import {montserrat} from './fonts';

export const BTCPrice = ({price, change}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (price == null) return null;
  const pop = spring({frame, fps, config: {damping: 14, mass: 0.8}});
  const x = interpolate(pop, [0, 1], [-90, 0]);
  const up = Number(change) >= 0;
  const color = up ? '#16c784' : '#ea3943';
  const arrow = up ? '▲' : '▼';
  const priceStr = '$' + Number(price).toLocaleString('en-US');
  const changeStr = (up ? '+' : '') + Number(change).toFixed(1) + '%';
  return (
    <div style={{
      position: 'absolute', top: 320, left: 56,
      display: 'flex', alignItems: 'center', gap: 14,
      background: 'rgba(12,14,18,0.92)', padding: '12px 22px 12px 14px',
      borderRadius: 18, transform: 'translateX(' + x + 'px)', opacity: pop,
      boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
    }}>
      <Img src={staticFile('logos/btc.png')} style={{width: 56, height: 56}} />
      <div style={{display: 'flex', flexDirection: 'column', lineHeight: 1.05}}>
        <div style={{fontFamily: montserrat, fontWeight: 800, fontSize: 36, color: 'white'}}>{priceStr}</div>
        <div style={{fontFamily: montserrat, fontWeight: 800, fontSize: 26, color: color}}>{arrow} {changeStr}</div>
      </div>
    </div>
  );
};
