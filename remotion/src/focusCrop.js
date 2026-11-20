// objectPosition that keeps a photo's subject (focus from focus.py) inside a cover-cropped box.
// Faces land in the upper part of the box (outfit below), other subjects in the middle.
export const focusPos = (p, boxW, boxH, fallback = '50% 30%') => {
  const f = p && p.focus;
  const a = p && Number(p.aspect);
  if (!f || !a) return fallback;
  const fit = a > boxW / boxH;                       // wider than the box -> height fits, crop the sides
  const sw = fit ? boxH * a : boxW, sh = fit ? boxH : boxW / a;
  const ty = f.face ? 0.36 : 0.5;
  const pct = (fc, size, box, t) => {
    const room = size - box;
    if (room < 1) return 50;
    return Math.min(Math.max((fc * size - t * box) / room, 0), 1) * 100;
  };
  return `${pct(f.x, sw, boxW, 0.5).toFixed(1)}% ${pct(f.y, sh, boxH, ty).toFixed(1)}%`;
};
