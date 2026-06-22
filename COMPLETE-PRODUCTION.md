# 🎬 Complete Video Production Pipeline

## Overview

This system automatically produces complete news videos with:
- ✅ Video clips from YouTube (cropped, no watermarks/tickers)
- ✅ Hindi voiceovers (Piper TTS at 1.25x speed)
- ✅ Beautiful Hindi captions (burned-in SRT)
- ✅ Automatic upload to Cloudflare R2

## 📋 Input Format

Paste JSON array with timestamps:

```json
[
  {
    "number": 1,
    "title": "शराब दुकान का विरोध",
    "script": "चौरी के कंधिया फाटक के पास...",
    "videoStart": "00:00:45",
    "videoEnd": "00:01:56"
  },
  {
    "number": 2,
    "title": "गंगा घाट पर बुजुर्ग की मौत",
    "script": "गोपीगंज के पिरोजपुर...",
    "videoStart": "00:01:56",
    "videoEnd": "00:03:07"
  }
]
```

**Required Fields:**
- `number`: Sequence number (1, 2, 3...)
- `title`: News headline
- `script`: Full news script (Hindi)
- `videoStart`: Start timestamp in YouTube video (`HH:MM:SS` or `MM:SS`)
- `videoEnd`: End timestamp in YouTube video

## 🚀 How to Use

### Step 1: Open Admin Panel
Visit: https://admin-five-peach.vercel.app

### Step 2: Select Production Mode
- **🎬 Complete Mode**: Video + Audio + Captions (select this!)
- 🎙️ Audio Only: Just voiceover + SRT

### Step 3: Enter YouTube URL
Example: `https://youtube.com/watch?v=YOUR_VIDEO_ID`

### Step 4: Paste JSON Scripts
Paste the JSON array with all news items and timestamps

### Step 5: Click "Start Production"
- Workflow triggers on GitHub Actions
- Wait ~15-20 minutes for completion
- Results appear automatically with video players

## 🎥 Video Processing Details

### 1. **YouTube Download (480p)**
```bash
yt-dlp -f "bestvideo[height<=480]+bestaudio" <URL>
```
- Downloads in 480p quality (smaller, faster)
- Saves bandwidth and processing time

### 2. **Smart Center Crop**
Automatically removes:
- **Top 8%**: Channel logo/watermark
- **Bottom 12%**: News ticker
- **Left/Right 6% each**: Decorative borders

Output: Clean 1280x720 (HD) center footage

### 3. **Intelligent Trimming**
- Extracts middle portion of video clip
- Matches voiceover duration exactly
- No awkward cuts or silence

### 4. **Voiceover Generation**
- Piper TTS with Hindi Pratham voice (male)
- 1.25x speed (energetic, professional)
- High quality, natural pronunciation

### 5. **Beautiful Captions**
- White text with thick black outline
- Semi-transparent background
- Readable on any video content
- Bottom-center aligned (40px margin)

### 6. **Final Stitching**
```bash
ffmpeg -i video.mp4 -i audio.wav -vf "subtitles=caption.srt" final.mp4
```
- Combines video + voiceover + burned captions
- Single MP4 file ready for upload

## 📦 Output Structure

All files uploaded to R2:

```
R2 Bucket (news.opanbaux.com):
├─ videos/
│  ├─ raw/
│  │  └─ source_<BATCH_ID>.mp4          # Original YouTube video
│  ├─ clips/
│  │  ├─ clip_<BATCH_ID>_1.mp4          # Cropped & trimmed clips
│  │  ├─ clip_<BATCH_ID>_2.mp4
│  │  └─ ...
│  └─ final/
│     ├─ final_<BATCH_ID>_1.mp4         # 🎬 COMPLETE VIDEOS
│     ├─ final_<BATCH_ID>_2.mp4
│     └─ ...
│
├─ voiceovers/
│  ├─ piper_<BATCH_ID>_1.wav
│  ├─ piper_<BATCH_ID>_2.wav
│  └─ ...
│
├─ captions/
│  ├─ piper_<BATCH_ID>_1.srt
│  ├─ piper_<BATCH_ID>_2.srt
│  └─ ...
│
└─ summaries/
   └─ final_batch_<BATCH_ID>.json       # All results with URLs
```

## 📊 Results JSON

```json
{
  "batchId": "1234567890",
  "youtubeUrl": "https://youtube.com/watch?v=...",
  "sourceVideoUrl": "https://news.opanbaux.com/videos/raw/source_1234567890.mp4",
  "totalItems": 20,
  "successCount": 20,
  "videos": [
    {
      "number": 1,
      "title": "शराब दुकान का विरोध",
      "status": "success",
      "finalVideoUrl": "https://news.opanbaux.com/videos/final/final_1234567890_1.mp4",
      "clipUrl": "https://news.opanbaux.com/videos/clips/clip_1234567890_1.mp4",
      "voiceoverUrl": "https://news.opanbaux.com/voiceovers/piper_1234567890_1.wav",
      "srtUrl": "https://news.opanbaux.com/captions/piper_1234567890_1.srt",
      "duration": 35
    }
  ]
}
```

## ⏱️ Processing Time

| Step | Duration |
|------|----------|
| Download video (480p, 20 min) | 2-3 min |
| Upload to R2 | 1-2 min |
| Extract 20 clips (crop + trim) | 4-5 min |
| Generate 20 voiceovers | 3-4 min |
| Stitch 20 final videos | 5-6 min |
| Upload everything | 2-3 min |
| **TOTAL** | **17-23 minutes** |

## 💰 Cost Analysis

### GitHub Actions (Free Tier)
- **Free quota**: 2000 minutes/month
- **Per run**: ~20 minutes
- **Daily capacity**: 100+ runs/month ✅

### Cloudflare R2 (Storage)
- **Storage**: $0.015/GB/month
- **Per batch**: ~200-300MB (20 videos)
- **Monthly**: ~$0.10-0.20 for daily batches ✅

### Total Cost
**Completely FREE** within GitHub/R2 free tiers!

## 🎯 Quality Settings

### Video
- **Resolution**: 1280x720 (HD)
- **Codec**: H.264 (libx264)
- **CRF**: 23 (high quality)
- **Preset**: medium (balanced)

### Audio
- **Format**: AAC
- **Bitrate**: 128kbps
- **Sample Rate**: 16kHz (Piper output)
- **Speed**: 1.25x (via Piper --length_scale 0.8)

### Captions
- **Font**: Arial (good Hindi support)
- **Size**: 28px
- **Style**: White + Black outline + Shadow
- **Position**: Bottom center (40px margin)

## 🛠️ Technical Stack

- **Video Download**: yt-dlp
- **Video Processing**: FFmpeg
- **Voiceover**: Piper TTS (hi_IN-pratham-medium)
- **Caption Format**: SRT (SubRip)
- **Storage**: Cloudflare R2 (S3-compatible)
- **Automation**: GitHub Actions
- **Admin Panel**: Vercel (Next.js API routes)

## 📝 Workflow Architecture

```
Admin Panel (Vercel)
    ↓ [Trigger]
GitHub Actions Workflow
    ↓
Step 1: process_videos.py
    ├─ Download YouTube (yt-dlp)
    ├─ Upload source to R2
    ├─ Crop center (remove watermarks)
    ├─ Trim to voiceover duration
    └─ Upload clips to R2
    ↓
Step 2: generate_voiceovers.py
    ├─ Generate voiceovers (Piper)
    ├─ Create SRT captions
    └─ Upload to R2
    ↓
Step 3: stitch_final_videos.py
    ├─ Download clips + audio + SRT
    ├─ Burn captions into video
    ├─ Combine with voiceover
    └─ Upload final videos to R2
    ↓
Results JSON → R2 → Admin Panel
```

## 🔧 Customization

### Adjust Crop Dimensions
Edit `scripts/process_videos.py`:

```python
def calculate_crop_filter(width, height):
    # Modify percentages:
    left_crop = int(width * 0.06)    # 6% from left
    right_crop = int(width * 0.06)   # 6% from right
    top_crop = int(height * 0.08)    # 8% from top
    bottom_crop = int(height * 0.12) # 12% from bottom
```

### Change Caption Style
Edit `scripts/stitch_final_videos.py`:

```python
subtitle_style = (
    "FontName=Arial,"
    "FontSize=28,"          # Larger/smaller
    "PrimaryColour=&H00FFFFFF,"  # Text color (BGR hex)
    "OutlineColour=&H00000000,"  # Outline color
    "MarginV=40"            # Distance from bottom
)
```

### Modify Voiceover Speed
Edit `scripts/generate_voiceovers.py`:

```python
'--length_scale', '0.8',  # 0.8 = 1.25x speed
                           # 0.9 = 1.11x speed
                           # 1.0 = normal speed
                           # 0.7 = 1.43x speed
```

## 🐛 Troubleshooting

### "YouTube download failed"
- Check if video is private/restricted
- Try with a different video
- Verify URL format is correct

### "Crop shows watermarks"
- Video might have different resolution
- Adjust crop percentages in `calculate_crop_filter()`
- Test with one video first

### "Voiceover too fast/slow"
- Adjust `--length_scale` parameter
- 0.8 = 1.25x speed (current)
- 1.0 = normal speed
- Smaller = faster, Larger = slower

### "Results not appearing"
- Wait full 20 minutes
- Check GitHub Actions tab for errors
- Verify R2 bucket permissions

## 📞 Support

Check logs in:
1. **GitHub Actions**: https://github.com/shivamupadhyay6501-lang/bhadohi1-tts-service/actions
2. **Vercel Logs**: https://vercel.com dashboard
3. **R2 Dashboard**: Cloudflare account

## 🎉 Success!

Your complete video production pipeline is now live and automated!

Every video will have:
- ✅ Professional Hindi voiceover (1.25x speed)
- ✅ Clean footage (no watermarks/tickers)
- ✅ Beautiful burned-in captions
- ✅ Ready for direct upload to social media

**Enjoy your automated video production! 🚀**
