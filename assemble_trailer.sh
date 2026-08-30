#!/bin/bash
# KUDBEE 90-Second Trailer Assembly
# Creates a cinematic trailer using FFmpeg

cd /opt/kudbee/outputs

# Create individual scene clips
mkdir -p /tmp/trailer_scenes

# Scene 1: Opening text (0-4s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=4:r=30" \
    -vf "drawtext=text='What if your ideas\\n could build themselves?':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-50:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_01.mp4 2>/dev/null

# Scene 2: KUDBEE title (4-8s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=4:r=30" \
    -vf "drawtext=text='KUDBEE':fontsize=120:fontcolor=#00d4ff:x=(w-text_w)/2:y=300:fade=t=in:st=0:d=0.5,drawtext=text='Think Box AI':fontsize=64:fontcolor=#7b2ff7:x=(w-text_w)/2:y=450:fade=t=in:st=0.5:d=0.5" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_02.mp4 2>/dev/null

# Scene 3: Specialized agents (8-14s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=6:r=30" \
    -vf "drawtext=text='Specialized agents\\n that collaborate':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-30:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_03.mp4 2>/dev/null

# Scene 4: Capabilities (14-20s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=6:r=30" \
    -vf "drawtext=text='Write • Code • Design • Analyze':fontsize:42:fontcolor=#00d4ff:x=(w-text_w)/2:y=(h-text_h)/2:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_04.mp4 2>/dev/null

# Scene 5: Persistent (20-26s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=6:r=30" \
    -vf "drawtext=text='Each one persistent':fontsize:40:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-20:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_05.mp4 2>/dev/null

# Scene 6: Purpose-built (26-32s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=6:r=30" \
    -vf "drawtext=text='Each one purpose-built':fontsize:40:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-20:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_06.mp4 2>/dev/null

# Scene 7: Memory (32-40s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=8:r=30" \
    -vf "drawtext=text='They remember\\n what they learn':fontsize=42:fontcolor=#7b2ff7:x=(w-text_w)/2:y=(h-text_h)/2-30:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_07.mp4 2>/dev/null

# Scene 8: One sentence in (40-48s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=8:r=30" \
    -vf "drawtext=text='One sentence in':fontsize=56:fontcolor=#00d4ff:x=(w-text_w)/2:y=(h-text_h)/2-30:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_08.mp4 2>/dev/null

# Scene 9: Finished production out (48-56s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=8:r=30" \
    -vf "drawtext=text='Finished production out':fontsize=56:fontcolor=#00d4ff:x=(w-text_w)/2:y=(h-text_h)/2:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_09.mp4 2>/dev/null

# Scene 10: Hardware (56-64s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=8:r=30" \
    -vf "drawtext=text='3x NVIDIA L40S • 256GB RAM':fontsize:28:fontcolor=#888888:x=(w-text_w)/2:y=(h-text_h)/2-20:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_10.mp4 2>/dev/null

# Scene 11: Models (64-75s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=11:r=30" \
    -vf "drawtext=text='GPT-OSS • ACE-Step\\nFLUX • LTX':fontsize=32:fontcolor=#666666:x=(w-text_w)/2:y=(h-text_h)/2-30:fade=t=in:st=0:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_11.mp4 2>/dev/null

# Scene 12: Final title (75-85s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=10:r=30" \
    -vf "drawtext=text='KUDBEE':fontsize=100:fontcolor=#00d4ff:x=(w-text_w)/2:y=300:fade=t=in:st=0:d=1,drawtext=text='Think Box AI':fontsize=60:fontcolor=#7b2ff7:x=(w-text_w)/2:y=420:fade=t=in:st=1:d=1" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_12.mp4 2>/dev/null

# Scene 13: CTA (85-90s)
ffmpeg -y -f lavfi -i "color=c=0a0a2e:s=1920x1080:d=5:r=30" \
    -vf "drawtext=text='kudbee.ai':fontsize:40:fontcolor=#ffffff:x=(w-text_w)/2:y=(h-text_h)/2:fade=t=in:st=0:d=1,fade=t=out:st=3:d=2" \
    -c:v libx264 -preset fast /tmp/trailer_scenes/scene_13.mp4 2>/dev/null

# Create concat file
> /tmp/trailer_scenes/concat.txt
for i in $(seq -w 1 13); do
    echo "file 'scene_${i}.mp4'" >> /tmp/trailer_scenes/concat.txt
done

# Concatenate video
ffmpeg -y -f concat -safe 0 -i /tmp/trailer_scenes/concat.txt -c copy /tmp/trailer_video.mp4 2>/dev/null

# Add narration
ffmpeg -y -i /tmp/trailer_video.mp4 -i /tmp/narration_full.wav -c:v copy -map 0:v:0 -map 1:a:0 -shortest /tmp/video_narration.mp4 2>/dev/null

# Add music (mix)
ffmpeg -y -i /tmp/video_narration.mp4 -i /tmp/trailer_music.wav -filter_complex "[0:a]volume=1.0[narr];[1:a]volume=0.25[musc];[narr][musc]amix=inputs=2:duration=first[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k ku3bee-trailer-v1.mp4 2>/dev/null

echo "=== TRAILER COMPLETE ==="
ls -lh ku3bee-trailer-v1.mp4
