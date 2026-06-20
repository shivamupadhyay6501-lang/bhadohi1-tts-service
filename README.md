# 🎙️ Bhadohi1 TTS Service - Piper on GitHub Actions

High-quality Hindi text-to-speech using Piper TTS, hosted entirely on GitHub Actions for **FREE**.

## Features

- ✅ **FREE** - No API costs, runs on GitHub Actions
- 🎯 **Hindi Voice** - Natural sounding Hindi TTS
- ⚡ **Fast** - 50 MB model, generates in seconds
- 🔄 **Automated** - Triggered via webhook from admin panel
- ☁️ **R2 Upload** - Automatically uploads audio & captions to R2

## How It Works

```
Admin Panel (Vercel) → Triggers GitHub Action
                          ↓
                    Downloads Piper (cached)
                          ↓
                    Generates voiceovers
                          ↓
                    Uploads to R2
                          ↓
                    Returns results
```

## Setup Instructions

### 1. Create GitHub Repository

1. Go to https://github.com/new
2. Name: `bhadohi1-tts-service` (or any name)
3. Visibility: **Public** (for free Actions)
4. Create repository

### 2. Add Secrets to Repository

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets (get values from your admin):

```
R2_ACCESS_KEY = your_r2_access_key
R2_SECRET_KEY = your_r2_secret_key
R2_ENDPOINT = your_r2_endpoint_url
R2_BUCKET = your_bucket_name
R2_PUBLIC_URL = your_public_cdn_url
```

### 3. Push Code to GitHub

```bash
cd c:\Projects\bone\bhadohi1\tts-service
git add .
git commit -m "Initial TTS service setup"
git remote add origin https://github.com/YOUR_USERNAME/bhadohi1-tts-service.git
git branch -M main
git push -u origin main
```

### 4. Get Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Name: "TTS Service Trigger"
4. Scopes: Check `repo` and `workflow`
5. Generate and **COPY the token**

### 5. Update Admin Panel

Add this to your Vercel admin panel to trigger the workflow.

## Manual Testing

### Test Workflow Manually

1. Go to your GitHub repo
2. Click **Actions** tab
3. Click **Generate Hindi Voiceovers with Piper**
4. Click **Run workflow**
5. Paste test JSON:

```json
[
  {
    "number": 1,
    "title": "परीक्षण समाचार",
    "fullText": "यह एक परीक्षण समाचार है। भदोही में आज एक महत्वपूर्ण घटना घटी।"
  }
]
```

6. Click **Run workflow**
7. Watch it run (takes ~2-3 minutes first time, 30 sec after caching)

## Performance

### First Run (No Cache)
- Download Piper: ~30 seconds
- Download Model: ~20 seconds  
- Generate voiceovers: ~5 sec per item
- Upload to R2: ~5 seconds
- **Total: ~2-3 minutes**

### Subsequent Runs (Cached)
- Load from cache: ~5 seconds
- Generate voiceovers: ~5 sec per item
- Upload to R2: ~5 seconds
- **Total: ~30-60 seconds**

## Voice Quality

- Better than Amazon Polly standard
- Natural Hindi pronunciation
- Consistent quality
- No robotic sound

## Cost

**$0.00** - Completely FREE!

GitHub Actions free tier:
- 2,000 minutes/month for public repos
- Each batch: ~1 minute
- Can run ~60 batches/day

## Troubleshooting

### Workflow fails with "Model not found"
- First run downloads model automatically
- Wait for cache to populate
- Subsequent runs will be fast

### R2 upload fails
- Check secrets are set correctly
- Verify R2 bucket exists
- Check R2 credentials have write permission

### Audio quality issues
- Model: `hi_IN-medium` (balanced)
- Can upgrade to `hi_IN-high` for better quality (slower)
- Edit workflow file, change model name

## Upgrading to High Quality

Edit `.github/workflows/generate-voiceover.yml`:

Replace:
```yaml
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/medium/hi_IN-medium.onnx
```

With:
```yaml
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/high/hi_IN-high.onnx
```

## Next Steps

1. Integrate with admin panel
2. Add webhook trigger
3. Test with real news
4. Monitor Actions usage
5. Consider upgrading to XTTS v2 for even better quality

## Support

Issues? Open an issue on GitHub or check Actions logs.
