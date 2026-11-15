// Shared timing helpers (used by NewsVideo and FiveHuVideo).

export const buildCaptions = (voiceover, durationInFrames, fps) => {
  const words = (voiceover || '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const totalMs = (durationInFrames / fps) * 1000;
  const per = totalMs / words.length;
  return words.map((text, i) => ({text, startMs: Math.round(i * per), endMs: Math.round((i + 1) * per)}));
};

// Frame boundaries for each scene, aligned to when its vo_segment words are actually spoken.
export const syncedBoundaries = (scenes, caps, durationInFrames, fps) => {
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

// [{from, dur}] per scene: speech-synced when possible, else script durations stretched to the voice.
export const sceneTimeline = (scenes, caps, durationInFrames, fps) => {
  const synced = syncedBoundaries(scenes, caps, durationInFrames, fps);
  if (synced) return scenes.map((s, i) => ({from: synced[i], dur: Math.max(1, synced[i + 1] - synced[i])}));
  const scriptTotal = scenes.reduce((a, s) => a + Number(s.duration), 0) || 1;
  const stretch = durationInFrames / (scriptTotal * fps);
  let acc = 0;
  return scenes.map((s, i) => {
    const segFrames = Math.round(Number(s.duration) * fps * stretch);
    const from = acc;
    acc += segFrames;
    return {from, dur: i === scenes.length - 1 ? Math.max(1, durationInFrames - from) : segFrames};
  });
};
