import React from 'react';
import {Composition, staticFile} from 'remotion';
import {parseMedia} from '@remotion/media-parser';
import {NewsVideo} from './NewsVideo';
import {DataScene} from './DataScene';

export const Root = () => {
  return (
    <>
      <Composition
        id="NewsVideo"
        component={NewsVideo}
        durationInFrames={450}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          scenes: [
            {image: 'img_1792651587110_1.png', duration: 4, on_screen_text: 'Bitcoin Seizure', vo_segment: 'China wants to seize over 61,800 Bitcoin', center: {type: 'none'}},
            {image: 'img_1792651587110_2.png', duration: 7, on_screen_text: '$5.7B Crypto Fraud', vo_segment: 'tied to a 5.7 billion dollar fraud', center: {type: 'stat', value: '5.7', prefix: '$', suffix: 'B', color: 'red', label: 'linked to the fraud'}},
            {image: 'img_1792651587110_3.png', duration: 4, on_screen_text: 'UK Court Ruling', vo_segment: 'affecting more than 102,000 investors', center: {type: 'coin', ticker: 'btc'}},
          ],
          voice: 'voice_1792651587110.mp3',
          voiceover: 'China wants to seize over 61,800 Bitcoin tied to a 5.7 billion dollar fraud affecting more than 102,000 investors',
          ticker: 'btc',
          btc_price: 67420,
          btc_change_24h: 2.4,
          fps: 30,
        }}
        calculateMetadata={async ({props}) => {
          const fps = props.fps || 30;
          let seconds = (props.scenes || []).reduce((a, s) => a + Number(s.duration), 0) || 15;
          try {
            const {slowDurationInSeconds} = await parseMedia({src: staticFile(props.voice), fields: {slowDurationInSeconds: true}, acknowledgeRemotionLicense: true});
            if (slowDurationInSeconds > 0.1) seconds = slowDurationInSeconds;
          } catch (e) {}
          return {durationInFrames: Math.max(1, Math.round(seconds * fps)), fps, width: 1080, height: 1920};
        }}
      />
      <Composition
        id="DataDemo"
        component={DataScene}
        durationInFrames={150}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          headline: 'Bitcoin ETF Outflows',
          value: 635,
          unit: 'M',
          label: 'pulled from Bitcoin ETFs in one day',
          sub: 'Biggest single-day outflow since June',
          bg: 'img_1792742573874_1.png',
          btc_price: 81486,
          btc_change_24h: -0.8,
        }}
      />
    </>
  );
};
