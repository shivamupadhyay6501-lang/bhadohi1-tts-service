# 📋 Complete Setup Guide - Piper TTS on GitHub Actions

Follow these steps **EXACTLY** to get Piper TTS working.

---

## ✅ Step 1: Create GitHub Repository (5 minutes)

1. Open browser: https://github.com/new

2. Fill in:
   - **Repository name:** `bhadohi1-tts-service`
   - **Visibility:** Select **Public** (required for free Actions)
   - **Initialize:** Don't check anything
   
3. Click **Create repository**

4. **Copy the repository URL** shown (e.g., `https://github.com/yourname/bhadohi1-tts-service.git`)

---

## ✅ Step 2: Push Code to GitHub (2 minutes)

Open PowerShell and run:

```powershell
cd c:\Projects\bone\bhadohi1\tts-service

git add .
git commit -m "Initial Piper TTS setup"

# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/bhadohi1-tts-service.git

git branch -M main
git push -u origin main
```

**Note:** Git will ask for credentials. Use:
- Username: Your GitHub username
- Password: Use **Personal Access Token** (NOT your GitHub password)

If you don't have a token yet, continue to Step 3.

---

## ✅ Step 3: Create GitHub Personal Access Token (3 minutes)

1. Go to: https://github.com/settings/tokens

2. Click **Generate new token** → Select **Generate new token (classic)**

3. Fill in:
   - **Note:** `Bhadohi TTS Service`
   - **Expiration:** 90 days (or No expiration)
   - **Scopes:** Check these boxes:
     - ✅ `repo` (all sub-items)
     - ✅ `workflow`

4. Click **Generate token**

5. **COPY THE TOKEN** (starts with `ghp_...`)
   - Save it somewhere safe!
   - You won't see it again!

---

## ✅ Step 4: Add Secrets to GitHub Repository (5 minutes)

1. Go to your repo: `https://github.com/YOUR_USERNAME/bhadohi1-tts-service`

2. Click **Settings** (top menu)

3. Left sidebar: Click **Secrets and variables** → **Actions**

4. Click **New repository secret** button

5. Add these secrets one by one:

### Secret 1:
```
Name: R2_ACCESS_KEY
Value: [Your R2 access key from Cloudflare]
```

### Secret 2:
```
Name: R2_SECRET_KEY
Value: [Your R2 secret key from Cloudflare]
```

### Secret 3:
```
Name: R2_ENDPOINT
Value: [Your R2 endpoint URL]
```

### Secret 4:
```
Name: R2_BUCKET
Value: [Your R2 bucket name]
```

### Secret 5:
```
Name: R2_PUBLIC_URL
Value: [Your public CDN URL]
```

**Verify:** You should see 5 secrets listed.

---

## ✅ Step 5: Test Workflow Manually (5 minutes)

1. Go to your repo on GitHub

2. Click **Actions** tab (top menu)

3. Left sidebar: Click **Generate Hindi Voiceovers with Piper**

4. Right side: Click **Run workflow** button

5. A form appears - paste this test data:

```json
[{"number":1,"title":"परीक्षण समाचार","fullText":"यह एक परीक्षण समाचार है। भदोही में आज मौसम बहुत अच्छा है।"}]
```

6. Click green **Run workflow** button

7. Refresh page - you'll see workflow running (yellow dot)

8. Click on the workflow run to see logs

9. Wait 2-3 minutes (first run downloads Piper)

10. When green checkmark appears, it's done! ✅

11. Check logs for R2 URLs of generated audio

---

## ✅ Step 6: Add GitHub Token to Vercel (3 minutes)

1. Go to Vercel dashboard: https://vercel.com/

2. Select project: **admin**

3. Click **Settings** → **Environment Variables**

4. Click **Add** button

5. Add:
   ```
   Name: GITHUB_TOKEN
   Value: ghp_your_token_here (paste token from Step 3)
   Environment: Production
   ```

6. Click **Save**

---

## ✅ Step 7: Update Admin Panel Code (2 minutes)

Edit file: `c:\Projects\bone\bhadohi1\admin\api\trigger-tts.js`

Find line:
```javascript
const GITHUB_OWNER = 'YOUR_GITHUB_USERNAME'; // Change this!
```

Replace with your actual GitHub username:
```javascript
const GITHUB_OWNER = 'your-actual-username';
```

Save file.

---

## ✅ Step 8: Deploy Updated Admin Panel (1 minute)

```powershell
cd c:\Projects\bone\bhadohi1\admin
vercel --prod
```

Wait for deployment to finish.

---

## ✅ Step 9: Test End-to-End (5 minutes)

1. Open admin panel: https://admin-five-peach.vercel.app

2. Paste some test news scripts

3. Click **Generate Voiceovers**

4. You'll see:
   - "✅ TTS generation started on GitHub Actions"
   - Message: "Check GitHub Actions tab for progress"

5. Open GitHub Actions tab in your browser

6. Watch the workflow run

7. When complete, audio files will be in R2!

---

## 🎉 Success Checklist

- [  ] GitHub repository created (public)
- [  ] Code pushed to GitHub
- [  ] Personal access token generated
- [  ] 5 secrets added to GitHub repo
- [  ] Manual workflow test successful
- [  ] GITHUB_TOKEN added to Vercel
- [  ] trigger-tts.js updated with username
- [  ] Admin panel redeployed
- [  ] End-to-end test successful

---

## 🐛 Troubleshooting

### "Repository not found" when pushing
- Check remote URL is correct
- Verify GitHub username in URL
- Use Personal Access Token as password

### Workflow doesn't appear in Actions tab
- Make sure code is pushed to `main` branch
- Check `.github/workflows/` folder exists
- Refresh GitHub page

### Workflow fails with "Secret not found"
- Go to Settings → Secrets → Actions
- Verify all 5 secrets are added
- Secret names must match exactly (case-sensitive)

### Audio quality is poor
- Default is `medium` quality
- Edit workflow file to use `hi_IN-high` model
- Tradeoff: Slower but better quality

### "GitHub token not configured" error
- Add GITHUB_TOKEN to Vercel environment variables
- Redeploy admin panel
- Token must have `repo` and `workflow` scopes

---

## 📊 Performance Expectations

### First Run (Cold Start)
- Download Piper binary: ~30 sec
- Download Hindi model: ~20 sec
- Generate voiceovers: ~5 sec per item
- Upload to R2: ~5 sec
- **Total: 2-3 minutes**

### Second Run Onwards (Cached)
- Load from cache: ~5 sec
- Generate voiceovers: ~5 sec per item
- Upload to R2: ~5 sec
- **Total: 30-60 seconds**

---

## 🔄 Daily Usage

1. Admin panel: Paste scripts → Click button
2. GitHub Actions: Runs automatically
3. R2: Files uploaded automatically
4. No manual intervention needed!

**Monthly limits:**
- 2,000 minutes free (public repo)
- Each run: ~1 minute
- Can process ~60 batches/day
- More than enough for daily news!

---

## 🚀 Next Level: XTTS v2

Once Piper is working, you can upgrade to XTTS v2 for even better quality:
- Near-human voice
- Voice cloning capability
- More natural emotions

Setup guide coming soon!

---

**Questions?** Open an issue on GitHub or check Actions logs for errors.
