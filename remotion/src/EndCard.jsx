import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';
import {anton, montserrat} from './fonts';

// Call-to-action card for ad channels (e.g. vikops): brand, site, phone.
export const EndCard = ({brand, url, phone, accent = '#D9C4A1'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 200}});
  const y = interpolate(enter, [0, 1], [40, 0]);
  const opacity = interpolate(frame, [0, 10], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', paddingBottom: 260}}>
      <div style={{
        translate: '0px ' + y + 'px', opacity,
        background: 'rgba(20,17,14,0.88)', borderRadius: 28, padding: '44px 70px',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)', border: '2px solid ' + accent,
      }}>
        {brand && <div style={{fontFamily: anton, fontSize: 112, letterSpacing: 10, color: 'white', lineHeight: 1}}>{brand}</div>}
        {url && <div style={{fontFamily: montserrat, fontWeight: 800, fontSize: 60, color: accent}}>{url}</div>}
        {phone && <div style={{fontFamily: montserrat, fontWeight: 700, fontSize: 44, color: 'white'}}>{phone}</div>}
      </div>
    </AbsoluteFill>
  );
};
