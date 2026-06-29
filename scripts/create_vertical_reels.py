#!/usr/bin/env python3
"""
Create Vertical Instagram Reels (9:16 format)
- Top: Headline bar with blue gradient
- Middle: Cropped news video (no audio)
- Bottom: Caption text area with yellow text
- Parallel batch processing for speed
"""

import os
import json
import subprocess
import boto3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import math

def run_command(cmd):
    """Run shell command and a output"""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise Exception(f"Command failed: {stderr}")
    return stdout

def upload_to_r2(file_path, remote_key, content_type='video/mp4'):
    """Upload file to Cloudflare R2"""
    r2_endpoint = os.environ.get('R2_ENDPOINT', '').strip()
    r2_access_key = os.environ.get('R2_ACCESS_KEY', '').strip()
    r2_secret_key = os.environ.get('R2_SECRET_KEY', '').strip()
    r2_bucket = os.environ.get('R2_BUCKET', '').strip()
    r2_public_url = os.environ.get('R2_PUBLIC_URL', '').strip()
    
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
    return public_url

def extract_thumbnail_from_clip(clip_path, output_path):
    """Extract thumbnail from middle of video clip"""
    # Get clip duration
    duration_cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        clip_path
    ]
    duration_output = run_command(duration_cmd)
    duration = float(duration_output.strip())
    
    # Extract frame from middle
    middle_time = duration / 2
    
    cmd = [
        'ffmpeg',
        '-ss', str(middle_time),
        '-i', clip_path,
        '-vframes', '1',
        '-vf', 'scale=360:640',  # Optimized size for fast loading
        '-q:v', '2',  # High quality
        '-y',
        output_path
    ]
    run_command(cmd)
    print(f"  📸 Thumbnail extracted from middle: {output_path}")

def create_vertical_reel(item, clip_path, voiceover_path, srt_path, timestamp):
    """
    Create vertical Instagram Reel format video - SIMPLE LAYOUT
    
    Layout:
    - Top 50%: Real news footage clip
    - Bottom 50%: AI Anchor video (trimmed from start to match voiceover duration)
    
    Total: 1080x1920 (9:16 vertical)
    """
    number = item['number']
    title = item['title']
    
    print(f"  🎨 Creating vertical reel for #{number}: {title}")
    
    output_filename = f"reel_{number}.mp4"
    
    # Get voiceover duration
    video_duration_cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        voiceover_path
    ]
    duration_output = run_command(video_duration_cmd)
    duration = float(duration_output.strip())
    
    print(f"  ⏱️ Voiceover duration: {duration:.2f}s")
    
    # Path to anchor video (in repo assets folder)
    anchor_video = 'assets/anchor.mp4'
    
    # Simple filter: Stack news clip on top, trimmed anchor on bottom
    # Trim anchor from 0:00 to duration (from start) with setpts for proper timing
    # Both videos will have keyframes at start = NO FREEZE!
    filter_complex = f"""
    [0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[top_news];
    [1:v]trim=start=0:duration={duration},setpts=PTS-STARTPTS,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[bottom_anchor];
    [top_news][bottom_anchor]vstack=inputs=2[v]
    """
    
    cmd = [
        'ffmpeg',
        '-i', clip_path,           # Input 0: News clip
        '-i', anchor_video,        # Input 1: Anchor video
        '-i', voiceover_path,      # Input 2: Voiceover audio
        '-filter_complex', filter_complex,
        '-map', '[v]',             # Use stacked video
        '-map', '2:a',             # Use voiceover audio only
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'faster',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-t', str(duration),       # Ensure output matches voiceover duration
        '-y',
        output_filename
    ]
    
    try:
        run_command(cmd)
        print(f"  ✅ Reel created: {output_filename}")
        
        # Generate thumbnail from clip (middle frame)
        thumbnail_filename = f"thumb_{number}.jpg"
        extract_thumbnail_from_clip(clip_path, thumbnail_filename)
        
        # Upload reel to R2
        reel_key = f"reels/reel_{timestamp}_{number}.mp4"
        reel_url = upload_to_r2(output_filename, reel_key, 'video/mp4')
        
        # Upload thumbnail to R2
        thumb_key = f"thumbnails/thumb_{timestamp}_{number}.jpg"
        thumb_url = upload_to_r2(thumbnail_filename, thumb_key, 'image/jpeg')
        
        # Cleanup
        os.remove(output_filename)
        os.remove(thumbnail_filename)
        
        return {
            'number': number,
            'title': title,
            'reelUrl': reel_url,
            'thumbnailUrl': thumb_url,
            'status': 'success'
        }
        
    except Exception as e:
        print(f"  ❌ Error creating reel #{number}: {e}")
        return {
            'number': number,
            'title': title,
            'status': 'failed',
            'error': str(e)
        }

def process_single_item(args):
    """Process a single news item (for parallel execution)"""
    item, timestamp = args
    number = item['number']
    
    try:
        print(f"\n{'='*60}")
        print(f"📰 Processing Item #{number}: {item['title']}")
        print(f"{'='*60}")
        
        # Use local clip path (no download needed!)
        clip_local = f"clip_{number}.mp4"
        
        # Voiceover comes from R2 (Piper TTS WAV format)
        voiceover_key = f"voiceovers/piper_{timestamp}_{number}.wav"
        voiceover_local = f"temp_voice_{number}.wav"
        
        # Download voiceover from R2
        download_from_r2(voiceover_key, voiceover_local)
        
        # Create vertical reel using local clip (no srt_path needed)
        result = create_vertical_reel(item, clip_local, voiceover_local, None, timestamp)
        
        # Cleanup temp files
        if os.path.exists(voiceover_local):
            os.remove(voiceover_local)
        
        print(f"✅ Item #{number} complete!")
        return result
        
    except Exception as e:
        print(f"❌ Error processing item #{number}: {e}")
        return {
            'number': number,
            'title': item.get('title', 'Unknown'),
            'status': 'failed',
            'error': str(e)
        }

def download_from_r2(remote_key, local_path):
    """Download file from R2"""
    r2_endpoint = os.environ.get('R2_ENDPOINT', '').strip()
    r2_access_key = os.environ.get('R2_ACCESS_KEY', '').strip()
    r2_secret_key = os.environ.get('R2_SECRET_KEY', '').strip()
    r2_bucket = os.environ.get('R2_BUCKET', '').strip()
    
    s3_client = boto3.client(
        's3',
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_access_key,
        aws_secret_access_key=r2_secret_key,
        region_name='auto'
    )
    
    s3_client.download_file(r2_bucket, remote_key, local_path)

def process_in_batches(news_items, timestamp, batch_size=5):
    """
    Process items in batches with parallel execution within each batch
    """
    total_items = len(news_items)
    num_batches = math.ceil(total_items / batch_size)
    
    print(f"\n📦 BATCH PROCESSING STARTED")
    print(f"   Total items: {total_items}")
    print(f"   Batch size: {batch_size}")
    print(f"   Number of batches: {num_batches}\n")
    
    all_results = []
    
    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_items)
        batch_items = news_items[start_idx:end_idx]
        batch_size_actual = len(batch_items)
        
        print(f"{'='*70}")
        print(f"🔄 BATCH {batch_num + 1}/{num_batches}")
        print(f"   Processing items {start_idx + 1} to {end_idx}")
        print(f"   Parallel workers: {batch_size_actual}")
        print(f"{'='*70}\n")
        
        # Prepare args for parallel processing
        batch_args = [(item, timestamp) for item in batch_items]
        
        # Process this batch in parallel
        with ThreadPoolExecutor(max_workers=batch_size_actual) as executor:
            batch_results = list(executor.map(process_single_item, batch_args))
        
        all_results.extend(batch_results)
        
        print(f"\n✅ BATCH {batch_num + 1} COMPLETE!")
        print(f"{'='*70}\n")
    
    return all_results

def main():
    print("🎬 VERTICAL REEL CREATOR STARTED\n")
    
    timestamp = int(os.environ.get('GITHUB_RUN_ID', '0'))
    news_data = json.loads(os.environ['NEWS_DATA'])
    
    print(f"📊 Batch ID: {timestamp}")
    print(f"📋 Total items to process: {len(news_data)}\n")
    
    # Process in batches of 5 (parallel within batch)
    results = process_in_batches(news_data, timestamp, batch_size=5)
    
    # Save results
    final_results = {
        'batchId': timestamp,
        'totalItems': len(news_data),
        'successCount': sum(1 for r in results if r.get('status') == 'success'),
        'reels': results
    }
    
    with open('reel_results.json', 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    
    # Upload results to R2
    results_key = f"summaries/reels_batch_{timestamp}.json"
    results_url = upload_to_r2('reel_results.json', results_key, 'application/json')
    
    # Cleanup: Remove all local clips and source video after processing
    print(f"\n🧹 Cleaning up local files...")
    for item in news_data:
        clip_file = f"clip_{item['number']}.mp4"
        if os.path.exists(clip_file):
            os.remove(clip_file)
            print(f"   Deleted: {clip_file}")
    
    if os.path.exists('source_video.mp4'):
        os.remove('source_video.mp4')
        print(f"   Deleted: source_video.mp4")
    
    print(f"✅ Local cleanup complete!\n")
    
    print(f"\n{'='*70}")
    print(f"🎊 VERTICAL REEL CREATION COMPLETE!")
    print(f"{'='*70}")
    print(f"✅ Successful: {final_results['successCount']}/{final_results['totalItems']}")
    print(f"📊 Results: {results_url}")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
