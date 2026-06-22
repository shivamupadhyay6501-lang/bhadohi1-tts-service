#!/usr/bin/env python3
"""
Stitch Final Videos
- Combines video clip + voiceover + SRT captions
- Burns beautiful Hindi captions into video
- Uploads final videos to R2
"""

import os
import json
import subprocess
import boto3
from pathlib import Path

def run_command(cmd):
    """Run shell command"""
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

def download_from_r2(remote_key, local_path):
    """Download file from R2"""
    print(f"⬇️ Downloading: {remote_key}")
    
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
    print(f"✅ Downloaded: {local_path}")

def upload_to_r2(file_path, remote_key, content_type='video/mp4'):
    """Upload file to R2"""
    print(f"☁️ Uploading: {remote_key}")
    
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
    print(f"✅ Uploaded: {public_url}")
    return public_url

def stitch_video(video_path, audio_path, srt_path, output_path):
    """
    Combine video + audio + burned-in SRT captions
    Beautiful Hindi caption styling with proper fonts
    """
    print(f"🎬 Stitching: {output_path}")
    
    # Escape SRT path for FFmpeg
    srt_escaped = srt_path.replace('\\', '/').replace(':', '\\:')
    
    # Beautiful caption style for Hindi
    subtitle_style = (
        "FontName=Arial,"
        "FontSize=28,"
        "Bold=1,"
        "PrimaryColour=&H00FFFFFF,"  # White text
        "OutlineColour=&H00000000,"  # Black outline
        "BackColour=&H80000000,"     # Semi-transparent black background
        "BorderStyle=1,"
        "Outline=3,"                 # Thick outline for readability
        "Shadow=2,"                  # Drop shadow
        "Alignment=2,"               # Bottom center
        "MarginV=40"                 # 40px from bottom
    )
    
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-i', audio_path,
        '-vf', f"subtitles={srt_escaped}:force_style='{subtitle_style}'",
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-shortest',  # Match shortest stream (audio or video)
        '-y',
        output_path
    ]
    
    run_command(cmd)
    print(f"✅ Final video created: {output_path}")

def main():
    print("🎞️ Starting Final Video Stitching\n")
    
    timestamp = int(os.environ.get('GITHUB_RUN_ID', '0'))
    
    # Load video and voiceover results
    with open('video_results.json', 'r', encoding='utf-8') as f:
        video_results = json.load(f)
    
    with open('results.json', 'r', encoding='utf-8') as f:
        voiceover_results = json.load(f)
    
    print(f"📦 Found {len(video_results['clips'])} video clips")
    print(f"🎙️ Found {len(voiceover_results)} voiceovers\n")
    
    final_videos = []
    
    # Match clips with voiceovers by number
    for video_clip in video_results['clips']:
        if video_clip.get('status') != 'success':
            print(f"⏭️ Skipping clip #{video_clip['number']} (failed)")
            continue
        
        number = video_clip['number']
        
        # Find matching voiceover
        voiceover = next((v for v in voiceover_results if v.get('number') == number), None)
        
        if not voiceover or voiceover.get('status') != 'success':
            print(f"⏭️ Skipping clip #{number} (no voiceover)")
            continue
        
        print(f"\n{'='*60}")
        print(f"🎬 Stitching #{number}: {video_clip['title']}")
        print(f"{'='*60}")
        
        try:
            # Download video clip
            video_key = video_clip['clipUrl'].split(f"{os.environ.get('R2_PUBLIC_URL', '')}/")[1]
            video_local = f"clip_{number}.mp4"
            download_from_r2(video_key, video_local)
            
            # Download voiceover
            audio_key = voiceover['audioUrl'].split(f"{os.environ.get('R2_PUBLIC_URL', '')}/")[1]
            audio_local = f"voiceover_{number}.wav"
            download_from_r2(audio_key, audio_local)
            
            # Download SRT
            srt_key = voiceover['srtUrl'].split(f"{os.environ.get('R2_PUBLIC_URL', '')}/")[1]
            srt_local = f"caption_{number}.srt"
            download_from_r2(srt_key, srt_local)
            
            # Stitch final video
            final_local = f"final_{number}.mp4"
            stitch_video(video_local, audio_local, srt_local, final_local)
            
            # Upload to R2
            final_key = f"videos/final/final_{timestamp}_{number}.mp4"
            final_url = upload_to_r2(final_local, final_key, 'video/mp4')
            
            final_videos.append({
                'number': number,
                'title': video_clip['title'],
                'finalVideoUrl': final_url,
                'clipUrl': video_clip['clipUrl'],
                'voiceoverUrl': voiceover['audioUrl'],
                'srtUrl': voiceover['srtUrl'],
                'duration': voiceover['duration'],
                'status': 'success'
            })
            
            # Cleanup local files
            for f in [video_local, audio_local, srt_local, final_local]:
                if os.path.exists(f):
                    os.remove(f)
            
            print(f"✅ Final video #{number} complete!\n")
            
        except Exception as e:
            print(f"❌ Error stitching #{number}: {e}\n")
            final_videos.append({
                'number': number,
                'title': video_clip['title'],
                'status': 'failed',
                'error': str(e)
            })
    
    # Save final results
    complete_results = {
        'batchId': timestamp,
        'youtubeUrl': video_results.get('youtubeUrl', ''),
        'sourceVideoUrl': video_results.get('sourceVideoUrl', ''),
        'totalItems': len(final_videos),
        'successCount': sum(1 for v in final_videos if v.get('status') == 'success'),
        'videos': final_videos
    }
    
    with open('final_results.json', 'w', encoding='utf-8') as f:
        json.dump(complete_results, f, indent=2, ensure_ascii=False)
    
    # Upload final results
    results_key = f"summaries/final_batch_{timestamp}.json"
    results_url = upload_to_r2('final_results.json', results_key, 'application/json')
    
    print(f"\n{'='*60}")
    print(f"🎊 COMPLETE VIDEO PRODUCTION FINISHED!")
    print(f"{'='*60}")
    print(f"✅ Successful: {complete_results['successCount']}/{complete_results['totalItems']}")
    print(f"📊 Results: {results_url}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
