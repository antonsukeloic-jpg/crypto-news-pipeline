import React from 'react';
import {Img, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';

export const CoinBadge = ({ticker}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!ticker) return null;
  const enter = spring({frame, fps, config: {damping: 14, mass: 0.8}});
  const scale = interpolate(enter, [0, 1], [0, 1]);
  const float = Math.sin((frame / fps) * 2.2) * 10;
  return (
    <div style={{position: 'absolute', top: 250, right: 56, scale: String(scale), translate: `0px ${float}px`}}>
      <Img src={staticFile(`logos/${ticker}.png`)} style={{width: 150, height: 150, filter: 'drop-shadow(0 10px 24px rgba(0,0,0,0.55))'}} />
    </div>
  );
};
