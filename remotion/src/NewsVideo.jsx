import React from 'react';
import {AbsoluteFill, Img, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, interpolate} from 'remotion';
import {Title} from './Title';
import {Captions} from './Captions';
import {BTCPrice} from './BTCPrice';
import {CenterModule} from './CenterModule';

const KenBurns = ({src, durationInFrames, zoomIn}) => {
  const frame = useCurrentFrame();
  const from = zoomIn ? 1 : 1.12;
  const to = zoomIn ? 1.12 : 1;
  const s = interpolate(frame, [0, durationInFrames], [from, to], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill>
      <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', scale: String(s)}} />
    </AbsoluteFill>
  );
};

const SceneMedia = ({scene, durationInFrames, zoomIn}) => {
  if (scene.video) {
    return (
      <AbsoluteFill>
        <OffthreadVideo src={staticFile(scene.video)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
    );
  }
  return <KenBurns src={staticFile(scene.image)} durationInFrames={durationInFrames} zoomIn={zoomIn} />;
};

const TopGradient = () => (
  <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0) 32%)'}} />
);

const buildCaptions = (voiceover, durationInFrames, fps) => {
  const words = (voiceover || '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const totalMs = (durationInFrames / fps) * 1000;
  const per = totalMs / words.length;
  return words.map((text, i) => ({text, startMs: Math.round(i * per), endMs: Math.round((i + 1) * per)}));
};

// Frame boundaries for each scene, aligned to when its vo_segment words are actually spoken.
const syncedBoundaries = (scenes, caps, durationInFrames, fps) => {
  const counts = scenes.map((s) => (s.vo_segment || '').trim().split(/\s+/).filter(Boolean).length);
  const total = counts.reduce((a, b) => a + b, 0);
  const tol = Math.max(3, Math.round(caps.length * 0.2));
  if (!caps.length || total === 0 || Math.abs(total - caps.length) > tol) return null;
  const b = [];
  let wi = 0;
  for (let i = 0; i < scenes.length; i++) {
    const startW = Math.min(wi, caps.length - 1);
    b.push(i === 0 ? 0 : Math.round((caps[startW].startMs / 1000) * fps));
    wi += counts[i];
  }
  b.push(durationInFrames);
  return b;
};

export const NewsVideo = ({scenes, voice, captions, voiceover, ticker, fps, btc_price, btc_change_24h}) => {
  const {durationInFrames} = useVideoConfig();
  const f = fps || 30;
  const caps = (captions && captions.length) ? captions : buildCaptions(voiceover, durationInFrames, f);

  const synced = syncedBoundaries(scenes, caps, durationInFrames, f);
  const sceneSeq = (s, i, from, dur) => (
    <Sequence key={i} from={from} durationInFrames={dur}>
      <SceneMedia scene={s} durationInFrames={dur} zoomIn={i % 2 === 0} />
      <TopGradient />
      <CenterModule center={s.center} />
      <Title text={s.on_screen_text} />
    </Sequence>
  );

  let seqs;
  if (synced) {
    seqs = scenes.map((s, i) => {
      const from = synced[i];
      const dur = Math.max(1, synced[i + 1] - from);
      return sceneSeq(s, i, from, dur);
    });
  } else {
    const scriptTotal = scenes.reduce((a, s) => a + Number(s.duration), 0) || 1;
    const stretch = durationInFrames / (scriptTotal * f);
    let acc = 0;
    seqs = scenes.map((s, i) => {
      const segFrames = Math.round(Number(s.duration) * f * stretch);
      const from = acc;
      acc += segFrames;
      const dur = (i === scenes.length - 1) ? Math.max(1, durationInFrames - from) : segFrames;
      return sceneSeq(s, i, from, dur);
    });
  }

  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      {seqs}
      {btc_price != null && <BTCPrice price={btc_price} change={btc_change_24h} />}
      {caps.length > 0 && <Captions captions={caps} />}
      <Audio src={staticFile(voice)} />
    </AbsoluteFill>
  );
};
