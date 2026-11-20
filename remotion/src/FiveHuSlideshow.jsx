import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate, Easing} from 'remotion';
import {FiveHuCarousel, carouselSlides} from './FiveHuCarousel';
import {inter, mono} from './fonts';

// TikTok version of the 5HU carousel: the same 4:5 slides as a 9:16 video over the run's own light techno
// (TikTok photo posts can't carry our track). Slide sits inside the safe area (clear of the top bar,
// the caption at the bottom and the buttons on the right); slow push-in, quick fade between slides.
const FPS = 30;
const SCALE = 0.8;                       // 1080x1350 slide -> 864x1080
const X = 108, Y = 190;
const secsFor = (s) => (s.kind === 'cover' ? 3.2 : s.kind === 'fact' ? 4.2 : s.kind === 'who' ? 3.2 : 2.8);

export const slideshowTimeline = (props) => {
  let from = 0;
  return carouselSlides(props).map((s, i) => {
    const dur = Math.round(secsFor(s) * FPS);
    const t = {i, from, dur};
    from += dur;
    return t;
  });
};
export const slideshowFrames = (props) => slideshowTimeline(props).reduce((a, t) => a + t.dur, 0) || FPS;

const Slide = ({props, i, dur}) => {
  const f = useCurrentFrame();
  const inP = interpolate(f, [0, 8], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const outP = interpolate(f, [dur - 6, dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const push = interpolate(f, [0, dur], [1, 1.035]);
  return (
    <div style={{position: 'absolute', left: X, top: Y, width: 1080 * SCALE, height: 1350 * SCALE, overflow: 'hidden', borderRadius: 18,
      opacity: Math.min(inP, outP), transform: `translateY(${(1 - inP) * 40}px)`}}>
      <div style={{width: 1080, height: 1350, transform: `scale(${SCALE * push})`, transformOrigin: 'top left'}}>
        <FiveHuCarousel {...props} slideIndex={i} />
      </div>
    </div>
  );
};

export const FiveHuSlideshow = (props) => {
  const {durationInFrames} = useVideoConfig();
  const frame = useCurrentFrame();
  const tl = slideshowTimeline(props);
  const cur = Math.max(0, tl.findIndex((t) => frame >= t.from && frame < t.from + t.dur));
  return (
    <AbsoluteFill style={{backgroundColor: '#0A0A0A'}}>
      <div style={{position: 'absolute', top: 150, left: X, right: X, display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 22,
        letterSpacing: 4, color: '#F5F5F2', opacity: 0.7}}>
        <span>5HU · WHO'S NEXT</span><span>{String(cur + 1).padStart(2, '0')}/{String(tl.length).padStart(2, '0')}</span>
      </div>
      {tl.map((t) => (
        <Sequence key={t.i} from={t.from} durationInFrames={t.dur}><Slide props={props} i={t.i} dur={t.dur} /></Sequence>
      ))}
      <div style={{position: 'absolute', top: Y + 1350 * SCALE + 34, left: X, display: 'flex', gap: 10}}>
        {tl.map((t) => (
          <div key={t.i} style={{width: t.i === cur ? 46 : 14, height: 8, borderRadius: 4, background: t.i === cur ? '#C8FF2E' : 'rgba(245,245,242,0.3)'}} />
        ))}
      </div>
      <Audio src={staticFile(props.music || 'music/5hu_techno.mp3')} loop volume={(fr) =>
        0.8 * interpolate(fr, [0, 10, durationInFrames - 30, durationInFrames - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
    </AbsoluteFill>
  );
};
