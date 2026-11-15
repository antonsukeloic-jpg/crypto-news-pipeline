#!/bin/bash
# Render-only test for the LT channel (no API credits): synthetic images + tone,
# Lithuanian captions with diacritics, no BTC overlay. The watcher picks it up
# and sends the result to Telegram like a real job.
S=/root/shared
mkdir -p $S/assets $S/jobs
i=1; for c in 0x224466 0x446622 0x662244; do
  ffmpeg -y -loglevel error -f lavfi -i "color=c=$c:s=720x1280:d=1" -frames:v 1 $S/assets/lt_img_fonttest_$i.png; i=$((i+1))
done
ffmpeg -y -loglevel error -f lavfi -i "sine=frequency=220:duration=15" -q:a 4 $S/assets/lt_voice_fonttest.mp3
python3 - <<'EOF'
import json
vo = "Žąsų ūkis Šiauliuose įgijo čempiono ėmėją"
words = vo.split(); per = 15000 / len(words)
job = {"comp": "main", "channel": "lt", "voice": "assets/lt_voice_fonttest.mp3", "output": "outputs/lt_video_fonttest.mp4",
       "ticker": "", "voiceover": vo,
       "captions": [{"text": w, "startMs": int(i * per), "endMs": int((i + 1) * per)} for i, w in enumerate(words)],
       "scenes": [
           {"image": "assets/lt_img_fonttest_1.png", "duration": 5, "on_screen_text": "Ąžuolų šventė Žemaitijoje", "vo_segment": "Žąsų ūkis",
            "center": {"type": "stat", "value": "12.5", "prefix": "", "suffix": "%", "color": "green", "label": "augo ūkių skaičius"}},
           {"image": "assets/lt_img_fonttest_2.png", "duration": 5, "on_screen_text": "Čia ęė įšų ūž", "vo_segment": "Šiauliuose įgijo", "center": {"type": "none"}},
           {"image": "assets/lt_img_fonttest_3.png", "duration": 5, "on_screen_text": "Šiauliai", "vo_segment": "čempiono ėmėją", "center": {"type": "none"}}]}
json.dump(job, open('/root/shared/jobs/lt_job_fonttest.json', 'w'), ensure_ascii=False)
print("test job dropped")
EOF
rm -f $S/archive/.done_lt_video_fonttest.mp4
chown -R 1000:1000 $S/assets $S/jobs
