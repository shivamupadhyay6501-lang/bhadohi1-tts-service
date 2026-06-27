#!/usr/bin/env python3
"""
Complete Video Production Pipeline
- Downloads YouTube video using cobalt.tools (480p)
- Extracts clips by timestamps
- Crops center (removes watermarks/borders)
- Trims to voiceover duration
- Uploads to R2
"""

import os
import json
import subprocess
import boto3
import requests
from pathlib import Path

def run_command(cmd, input_text=None):
    """Run shell command and return output"""
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if input_text else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=isinstance(cmd, str)
    )
    stdout, stderr = process.communicate(input=input_text)
    if process.returncode != 0:
        raise Exception(f"Command failed: {' '.join(cmd) if isinstance(cmd, list) else cmd}\n{stderr}")
    return stdout

def download_youtube_video_with_cobalt(url, output_path):
    """Download YouTube video using cobalt.tools API (free, 20 requests/hour)"""
    print(f"📥 Downloading video via cobalt.tools from: {url}")
    
    import requests
    import time
    
    # Clean URL (remove tracking parameters)
    if '?' in url:
        clean_url = url.split('?')[0]
    else:
        clean_url = url
    
    print(f"🔗 Clean URL: {clean_url}")
    print(f"🌐 Sending request to cobalt.tools API...")
    
    # cobalt.tools API endpoint
    api_url = "https://api.cobalt.tools/api/json"
    
    # Request payload
    payload = {
        "url": clean_url,
        "vQuality": "480",  # Low quality (480p) for faster processing
        "filenamePattern": "basic",
        "isAudioOnly": False,
        "disableMetadata": True
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # Send POST request to cobalt API
        print(f"⏳ Requesting video download URL...")
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        if not response.ok:
            raise Exception(f"cobalt.tools API error: {response.status_code} - {response.text}")
        
        result = response.json()
        print(f"📊 cobalt.tools response: {result.get('status', 'unknown')}")
        
        # Extract download URL from response
        download_url = None
        
        # cobalt returns different response formats based on status
        if result.get('status') == 'redirect':
            # Direct download URL
            download_url = result.get('url')
        elif result.get('status') == 'stream':
            # Streaming URL
            download_url = result.get('url')
        elif result.get('status') == 'picker':
            # Multiple quality options - pick first one
            picker_items = result.get('picker', [])
            if picker_items and len(picker_items) > 0:
                download_url = picker_items[0].get('url')
        
        if not download_url:
            raise Exception(f"No download URL in cobalt response. Full response: {result}")
        
        print(f"🔗 Video download URL obtained: {download_url[:100]}...")
        print(f"⬇️ Downloading video file...")
        
        # Download video with progress tracking
        video_response = requests.get(download_url, stream=True, timeout=900)
        
        if not video_response.ok:
            raise Exception(f"Video download failed: {video_response.status_code}")
        
        total_size = int(video_response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (20*1024*1024) == 0:  # Log every 20MB
                        progress = (downloaded / total_size) * 100
                        print(f"📥 Progress: {progress:.1f}% ({downloaded//1024//1024}MB/{total_size//1024//1024}MB)")
        
        print(f"✅ Video downloaded successfully: {output_path}")
        return output_path
        
    except requests.exceptions.Timeout:
        raise Exception("cobalt.tools API timeout (30s). Try again later.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"cobalt.tools request failed: {str(e)}")
    except Exception as e:
        raise Exception(f"cobalt.tools download failed: {str(e)}")

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    output = run_command(cmd)
    return float(output.strip())

def get_video_resolution(video_path):
    """Get video resolution (width, height)"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=p=0',
        video_path
    ]
    output = run_command(cmd)
    width, height = output.strip().split(',')
    return int(width), int(height)

def calculate_crop_filter(width, height):
    """
    Calculate balanced center crop to remove watermarks/borders
    
    Crop strategy:
    - Left: 8% (border)
    - Right: 17% (SATYAM NEWS logo area - increased from 12%)
    - Top: 10% (header area)
    - Bottom: 22% (news ticker strip)
    
    Output: Cropped area suitable for 9:16 vertical format
    """
    # Calculate crop amounts
    left_crop = int(width * 0.08)    # 8% from left
    right_crop = int(width * 0.17)   # 17% from right (SATYAM NEWS logo - increased!)
    top_crop = int(height * 0.10)    # 10% from top
    bottom_crop = int(height * 0.22) # 22% from bottom (ticker)
    
    # Crop dimensions
    crop_width = width - left_crop - right_crop
    crop_height = height - top_crop - bottom_crop
    
    # Position (where to start crop)
    x_offset = left_crop
    y_offset = top_crop
    
    print(f"   Original: {width}x{height}")
    print(f"   Crop: L={left_crop}px R={right_crop}px T={top_crop}px B={bottom_crop}px")
    print(f"   Result: {crop_width}x{crop_height}")
    
    return f"crop={crop_width}:{crop_height}:{x_offset}:{y_offset}"

def timestamp_to_seconds(timestamp):
    """Convert HH:MM:SS or MM:SS to seconds"""
    parts = timestamp.split(':')
    if len(parts) == 3:
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = map(int, parts)
        return m * 60 + s
    else:
        return int(parts[0])

def extract_and_crop_clip(source_video, start_time, end_time, output_path, crop_filter):
    """Extract clip from source video and apply center crop with FREQUENT KEYFRAMES"""
    print(f"✂️ Extracting clip: {start_time} to {end_time}")
    
    # Convert timestamps to seconds for calculation
    start_seconds = timestamp_to_seconds(start_time)
    end_seconds = timestamp_to_seconds(end_time)
    duration = end_seconds - start_seconds
    
    cmd = [
        'ffmpeg',
        '-ss', start_time,        # ✅ Seek BEFORE input (faster, accurate)
        '-i', source_video,
        '-t', str(duration),      # Duration instead of end time
        '-vf', crop_filter,
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'fast',
        '-g', '15',               # ✅ GOP size 15 (keyframe every 0.5s @ 30fps)
        '-keyint_min', '15',      # ✅ Minimum keyframe interval
        '-sc_threshold', '0',     # ✅ Disable scene change detection
        '-force_key_frames', 'expr:gte(t,0)',  # ✅ Force keyframe at start
        '-c:a', 'aac',
        '-b:a', '128k',
        '-y',
        output_path
    ]
    
    run_command(cmd)
    print(f"✅ Clip extracted with frequent keyframes (no freeze!): {output_path}")
    return output_path

def trim_clip_to_duration(input_clip, target_duration, output_path):
    """
    Trim clip to match target duration by extracting middle portion
    RE-ENCODE with keyframe at start (no freeze!)
    """
    clip_duration = get_video_duration(input_clip)
    
    if clip_duration <= target_duration:
        # Clip shorter or equal, use as-is
        print(f"⏱️ Clip duration ({clip_duration}s) <= target ({target_duration}s), using full clip")
        os.rename(input_clip, output_path)
        return output_path
    
    # Extract middle portion
    excess = clip_duration - target_duration
    start_offset = excess / 2
    
    print(f"⏱️ Trimming to {target_duration}s with forced keyframe at start (no freeze!)")
    
    cmd = [
        'ffmpeg',
        '-ss', str(start_offset),      # ✅ Seek BEFORE input
        '-i', input_clip,
        '-t', str(target_duration),
        '-c:v', 'libx264',             # ✅ RE-ENCODE (not copy!)
        '-crf', '23',
        '-preset', 'fast',
        '-g', '15',                    # ✅ Keyframe every 0.5s
        '-keyint_min', '15',           # ✅ Minimum keyframe interval
        '-sc_threshold', '0',          # ✅ Disable scene detection
        '-force_key_frames', 'expr:eq(n,0)',  # ✅ Force keyframe at frame 0
        '-c:a', 'aac',
        '-b:a', '128k',
        '-y',
        output_path
    ]
    
    run_command(cmd)
    
    # Remove temp file
    if os.path.exists(input_clip):
        os.remove(input_clip)
    
    print(f"✅ Clip trimmed with keyframe at start (instant playback!): {output_path}")
    return output_path

def upload_to_r2(file_path, remote_key, content_type='video/mp4'):
    """Upload file to Cloudflare R2"""
    print(f"☁️ Uploading to R2: {remote_key}")
    
    r2_endpoint = os.environ.get('R2_ENDPOINT', '').strip()
    r2_access_key = os.environ.get('R2_ACCESS_KEY', '').strip()
    r2_secret_key = os.environ.get('R2_SECRET_KEY', '').strip()
    r2_bucket = os.environ.get('R2_BUCKET', '').strip()
    r2_public_url = os.environ.get('R2_PUBLIC_URL', '').strip()
    
    if not all([r2_endpoint, r2_access_key, r2_secret_key, r2_bucket, r2_public_url]):
        raise Exception("Missing R2 configuration")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_access_key,
        aws_secret_access_key=r2_secret_key,
        region_name='auto'
    )
    
    with open(file_path, 'rb') as f:
        s3_client.put_object(
            Bucket=r2_bucket,
            Key=remote_key,
            Body=f,
            ContentType=content_type
        )
    
    public_url = f"{r2_public_url}/{remote_key}"
    print(f"✅ Uploaded: {public_url}")
    return public_url

def main():
    print("🎬 Starting Complete Video Production Pipeline\n")
    
    # Parse input
    youtube_url = os.environ['YOUTUBE_URL']
    news_data = json.loads(os.environ['NEWS_DATA'])
    timestamp = int(os.environ.get('GITHUB_RUN_ID', '0'))
    
    print(f"📺 YouTube URL: {youtube_url}")
    print(f"📋 Processing {len(news_data)} news items\n")
    
    # Step 1: Download source video using cobalt.tools
    source_video = 'source_video.mp4'
    download_youtube_video_with_cobalt(youtube_url, source_video)
    
    # Get video properties
    width, height = get_video_resolution(source_video)
    print(f"📐 Video resolution: {width}x{height}")
    
    crop_filter = calculate_crop_filter(width, height)
    print(f"✂️ Crop filter: {crop_filter}\n")
    
    # Step 2: Don't upload source video (save storage!)
    # source_key = f"videos/raw/source_{timestamp}.mp4"
    # source_url = upload_to_r2(source_video, source_key, 'video/mp4')
    print(f"✅ Source video kept local (not uploaded to R2)\n")
    
    # Step 3: Process each news item (keep clips local)
    video_clips = []
    
    for item in news_data:
        number = item['number']
        title = item['title']
        video_start = item['videoStart']
        video_end = item['videoEnd']
        
        print(f"\n{'='*60}")
        print(f"📰 Processing #{number}: {title}")
        print(f"{'='*60}")
        
        try:
            # Calculate expected voiceover duration (estimate: 150 words/min @ 1.25x speed)
            script = item.get('script', '')
            word_count = len(script.split())
            voiceover_duration = (word_count / 150) * 60 * 0.8  # 0.8 for 1.25x speed
            
            print(f"📝 Script: {len(script)} chars, ~{word_count} words")
            print(f"⏱️ Expected voiceover: ~{voiceover_duration:.1f}s")
            
            # Extract clip
            raw_clip = f"clip_{number}_raw.mp4"
            extract_and_crop_clip(
                source_video,
                video_start,
                video_end,
                raw_clip,
                crop_filter
            )
            
            # Trim to voiceover duration
            trimmed_clip = f"clip_{number}.mp4"
            trim_clip_to_duration(raw_clip, voiceover_duration, trimmed_clip)
            
            # Don't upload clip to R2 (save storage! - will be used locally by reel creator)
            # clip_key = f"videos/clips/clip_{timestamp}_{number}.mp4"
            # clip_url = upload_to_r2(trimmed_clip, clip_key, 'video/mp4')
            
            print(f"✅ Clip saved locally: {trimmed_clip}")
            
            video_clips.append({
                'number': number,
                'title': title,
                'localClipPath': trimmed_clip,  # Keep local path instead of URL
                'duration': voiceover_duration,
                'status': 'success'
            })
            
            # Don't cleanup yet - reel creator will need these files!
            # if os.path.exists(trimmed_clip):
            #     os.remove(trimmed_clip)
            
            print(f"✅ Clip #{number} processed successfully\n")
            
        except Exception as e:
            print(f"❌ Error processing clip #{number}: {e}\n")
            video_clips.append({
                'number': number,
                'title': title,
                'status': 'failed',
                'error': str(e)
            })
    
    # Step 4: Save results
    results = {
        'batchId': timestamp,
        'youtubeUrl': youtube_url,
        'totalItems': len(news_data),
        'successCount': sum(1 for c in video_clips if c.get('status') == 'success'),
        'clips': video_clips
    }
    
    with open('video_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Upload results
    results_key = f"summaries/video_batch_{timestamp}.json"
    results_url = upload_to_r2('video_results.json', results_key, 'application/json')
    
    print(f"\n{'='*60}")
    print(f"🎉 VIDEO PROCESSING COMPLETE!")
    print(f"{'='*60}")
    print(f"✅ Successful: {results['successCount']}/{results['totalItems']}")
    print(f"📊 Results: {results_url}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
