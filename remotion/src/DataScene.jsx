import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Easing} from 'remotion';
import {montserrat, anton} from './fonts';
import {Title} from './Title';
import {BTCPrice} from './BTCPrice';

const RED = '#ea3943';
const GRID = 'rgba(255,255,255,0.045)';

const BgImage = ({src}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1.04, 1.13], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill>
      <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover', scale: String(scale), filter: 'blur(7px) brightness(0.5)'}} />
      <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(6,8,13,0.82), rgba(6,8,13,0.58) 40%, rgba(6,8,13,0.9))'}} />
    </AbsoluteFill>
  );
};

const Grid = () => {
  const lines = [];
  for (let i = 1; i < 12; i++) lines.push(<div key={'h' + i} style={{position: 'absolute', left: 0, right: 0, top: (1920 / 12) * i, height: 1, background: GRID}} />);
  for (let i = 1; i < 7; i++) lines.push(<div key={'v' + i} style={{position: 'absolute', top: 0, bottom: 0, left: (1080 / 7) * i, width: 1, background: GRID}} />);
  return <AbsoluteFill>{lines}</AbsoluteFill>;
};

const BarChart = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const data = [120, -80, 60, -150, -210, -635];
  const maxAbs = 635;
  const barW = 110, gap = 28;
  const totalW = data.length * barW + (data.length - 1) * gap;
  const startX = (1080 - totalW) / 2;
  const baseY = 1470;
  const maxH = 300;
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 80, right: 80, top: baseY, height: 2, background: 'rgba(255,255,255,0.22)'}} />
      {data.map((v, i) => {
        const grow = spring({frame: frame - 34 - i * 3, fps, config: {damping: 14, mass: 0.6}});
        const h = (Math.abs(v) / maxAbs) * maxH * grow;
        const up = v >= 0;
        const x = startX + i * (barW + gap);
        const isLast = i === data.length - 1;
        return (
          <div key={i} style={{
            position: 'absolute', left: x, width: barW,
            top: up ? baseY - h : baseY, height: Math.max(0, h),
            background: isLast ? RED : (up ? 'rgba(22,199,132,0.5)' : 'rgba(234,57,67,0.38)'),
            borderRadius: 6, boxShadow: isLast ? '0 0 34px rgba(234,57,67,0.65)' : 'none',
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

export const DataScene = ({headline = 'Bitcoin ETF Outflows', value = 635, unit = 'M', label = 'pulled from Bitcoin ETFs in one day', sub = 'Biggest single-day outflow since June', bg = null, btc_price = 81486, btc_change_24h = -0.8}) => {
  const frame = useCurrentFrame();
  const prog = interpolate(frame, [15, 55], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const current = Math.round(value * prog);
  const numStr = '-$' + current + unit;
  const numOpacity = interpolate(frame, [12, 22], [0, 1], {extrapolateRight: 'clamp'});
  const labelOpacity = interpolate(frame, [44, 58], [0, 1], {extrapolateRight: 'clamp'});
  const subOpacity = interpolate(frame, [74, 88], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: '#0b0e14'}}>
      {bg ? <BgImage src={bg} /> : null}
      <Grid />
      <AbsoluteFill style={{background: 'radial-gradient(58% 38% at 50% 40%, rgba(234,57,67,0.18), rgba(0,0,0,0) 70%)'}} />
      <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', paddingTop: 540}}>
        <div style={{fontFamily: anton, fontSize: 230, color: RED, lineHeight: 0.9, opacity: numOpacity, textShadow: '0 10px 55px rgba(234,57,67,0.5)'}}>{numStr}</div>
        <div style={{fontFamily: montserrat, fontWeight: 700, fontSize: 40, color: 'rgba(255,255,255,0.88)', marginTop: 26, opacity: labelOpacity, textAlign: 'center', maxWidth: 860, textShadow: '0 2px 10px rgba(0,0,0,0.8)'}}>{label}</div>
      </AbsoluteFill>
      <BarChart />
      <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 230}}>
        <div style={{fontFamily: montserrat, fontWeight: 800, fontSize: 46, color: 'white', textAlign: 'center', opacity: subOpacity, maxWidth: 900, textShadow: '0 4px 18px rgba(0,0,0,0.9)'}}>{sub}</div>
      </AbsoluteFill>
      <Title text={headline} />
      {btc_price != null && <BTCPrice price={btc_price} change={btc_change_24h} />}
    </AbsoluteFill>
  );
};
