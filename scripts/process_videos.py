#!/usr/bin/env python3
"""
Complete Video Production Pipeline
- Downloads YouTube video (480p)
- Extracts clips by timestamps
- Crops center (removes watermarks/borders)
- Trims to voiceover duration
- Uploads to R2
"""

import os
import json
import subprocess
import boto3
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

def download_youtube_video(url, output_path):
    """Download YouTube video in 480p quality"""
    print(f"📥 Downloading video from: {url}")
    
    cmd = [
        'yt-dlp',
        url,
        '-f', 'bestvideo[height<=480]+bestaudio/best[height<=480]',
        '-o', output_path,
        '--merge-output-format', 'mp4',
        '--no-playlist'
    ]
    
    run_command(cmd)
    print(f"✅ Video downloaded: {output_path}")
    return output_path

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
    Calculate safe center crop to remove watermarks/borders
    
    Assumptions based on typical news channel layout:
    - Top watermark: 8% of height
    - Bottom ticker: 12% of height
    - Left border: 6% of width
    - Right border: 6% of width
    
    Output: 1280x720 (HD) after crop
    """
    # Calculate safe area
    left_crop = int(width * 0.06)
    right_crop = int(width * 0.06)
    top_crop = int(height * 0.08)
    bottom_crop = int(height * 0.12)
    
    # Crop dimensions
    crop_width = width - left_crop - right_crop
    crop_height = height - top_crop - bottom_crop
    
    # Ensure 16:9 aspect ratio
    target_aspect = 16 / 9
    current_aspect = crop_width / crop_height
    
    if current_aspect > target_aspect:
        # Too wide, reduce width
        crop_width = int(crop_height * target_aspect)
    else:
        # Too tall, reduce height
        crop_height = int(crop_width / target_aspect)
    
    # Recalculate position to center the crop
    x_offset = (width - crop_width) // 2
    y_offset = (height - crop_height) // 2
    
    return f"crop={crop_width}:{crop_height}:{x_offset}:{y_offset},scale=1280:720"

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
    """Extract clip from source video and apply center crop"""
    print(f"✂️ Extracting clip: {start_time} to {end_time}")
    
    cmd = [
        'ffmpeg',
        '-i', source_video,
        '-ss', start_time,
        '-to', end_time,
        '-vf', crop_filter,
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-y',
        output_path
    ]
    
    run_command(cmd)
    print(f"✅ Clip extracted: {output_path}")
    return output_path

def trim_clip_to_duration(input_clip, target_duration, output_path):
    """
    Trim clip to match target duration by extracting middle portion
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
    
    print(f"⏱️ Trimming to {target_duration}s (extracting middle from {clip_duration}s clip)")
    
    cmd = [
        'ffmpeg',
        '-i', input_clip,
        '-ss', str(start_offset),
        '-t', str(target_duration),
        '-c', 'copy',
        '-y',
        output_path
    ]
    
    run_command(cmd)
    
    # Remove temp file
    if os.path.exists(input_clip):
        os.remove(input_clip)
    
    print(f"✅ Clip trimmed: {output_path}")
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
    
    # Step 1: Download source video
    source_video = 'source_video.mp4'
    download_youtube_video(youtube_url, source_video)
    
    # Get video properties
    width, height = get_video_resolution(source_video)
    print(f"📐 Video resolution: {width}x{height}")
    
    crop_filter = calculate_crop_filter(width, height)
    print(f"✂️ Crop filter: {crop_filter}\n")
    
    # Step 2: Upload source video to R2
    source_key = f"videos/raw/source_{timestamp}.mp4"
    source_url = upload_to_r2(source_video, source_key, 'video/mp4')
    print(f"📦 Source video available at: {source_url}\n")
    
    # Step 3: Process each news item
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
            
            # Upload clip to R2
            clip_key = f"videos/clips/clip_{timestamp}_{number}.mp4"
            clip_url = upload_to_r2(trimmed_clip, clip_key, 'video/mp4')
            
            video_clips.append({
                'number': number,
                'title': title,
                'clipUrl': clip_url,
                'duration': voiceover_duration,
                'status': 'success'
            })
            
            # Cleanup
            if os.path.exists(trimmed_clip):
                os.remove(trimmed_clip)
            
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
        'sourceVideoUrl': source_url,
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
