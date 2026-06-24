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
    """Run shell command and return output"""
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

def create_vertical_reel(item, clip_path, voiceover_path, srt_path, timestamp):
    """
    Create vertical Instagram Reel format video
    
    Layout:
    - Top 15%: Headline bar (blue gradient + white text)
    - Middle 37%: Video clip (white border frame)
    - Bottom 48%: Caption area (yellow text on dark bg)
    
    Total: 1080x1920 (9:16 vertical)
    """
    number = item['number']
    title = item['title']
    
    print(f"  🎨 Creating vertical reel for #{number}: {title}")
    
    output_filename = f"reel_{number}.mp4"
    
    # Escape title for FFmpeg drawtext
    title_escaped = title.replace("'", "'\\''").replace(":", "\\:")
    
    # Get video duration for color sources
    video_duration_cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        voiceover_path
    ]
    duration_output = run_command(video_duration_cmd)
    duration = float(duration_output.strip())
    
    # Complex filter for vertical reel layout
    # All three sections must be 1080px wide for vstack to work
    # Using Noto Sans (has Hindi/Devanagari support in fonts-noto package)
    filter_complex = f"""
    color=c=#1e3a8a:s=1080x288:d={duration}[top_bar];
    [top_bar]drawtext=text='{title_escaped}':fontfile=/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf:fontsize=44:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:borderw=3:bordercolor=black[top_with_text];
    [0:v]scale=940:700:force_original_aspect_ratio=decrease,pad=940:700:(ow-iw)/2:(oh-ih)/2:black,pad=1010:730:35:15:white[video_inner];
    [video_inner]pad=1080:730:35:0:black[video_framed];
    color=c=#000000@0.85:s=1080x902:d={duration}[bottom_area];
    [bottom_area]subtitles={srt_path}:force_style='FontName=Noto Sans,FontSize=42,PrimaryColour=&H00FFD700,OutlineColour=&H00000000,Outline=3,BorderStyle=1,Alignment=1,MarginL=50,MarginR=50,MarginV=60'[bottom_with_subs];
    [top_with_text][video_framed][bottom_with_subs]vstack=inputs=3[v]
    """
    
    cmd = [
        'ffmpeg',
        '-i', clip_path,
        '-i', voiceover_path,
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-map', '1:a',  # Audio from voiceover only
        '-c:v', 'libx264',
        '-crf', '26',
        '-preset', 'faster',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-shortest',
        '-y',
        output_filename
    ]
    
    try:
        run_command(cmd)
        print(f"  ✅ Reel created: {output_filename}")
        
        # Upload to R2
        reel_key = f"reels/reel_{timestamp}_{number}.mp4"
        reel_url = upload_to_r2(output_filename, reel_key, 'video/mp4')
        
        # Cleanup
        os.remove(output_filename)
        
        return {
            'number': number,
            'title': title,
            'reelUrl': reel_url,
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
        
        # Download clip, voiceover, and SRT from R2
        clip_key = f"videos/clips/clip_{timestamp}_{number}.mp4"
        voiceover_key = f"voiceovers/piper_{timestamp}_{number}.wav"
        srt_key = f"captions/piper_{timestamp}_{number}.srt"
        
        clip_local = f"temp_clip_{number}.mp4"
        voiceover_local = f"temp_voice_{number}.wav"
        srt_local = f"temp_srt_{number}.srt"
        
        # Download from R2
        download_from_r2(clip_key, clip_local)
        download_from_r2(voiceover_key, voiceover_local)
        download_from_r2(srt_key, srt_local)
        
        # Create vertical reel
        result = create_vertical_reel(item, clip_local, voiceover_local, srt_local, timestamp)
        
        # Cleanup temp files
        for f in [clip_local, voiceover_local, srt_local]:
            if os.path.exists(f):
                os.remove(f)
        
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
    
    print(f"\n{'='*70}")
    print(f"🎊 VERTICAL REEL CREATION COMPLETE!")
    print(f"{'='*70}")
    print(f"✅ Successful: {final_results['successCount']}/{final_results['totalItems']}")
    print(f"📊 Results: {results_url}")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
