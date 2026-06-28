import os
import json
import asyncio
import boto3
import edge_tts
from pathlib import Path

def generate_srt(text, duration):
    """Generate simple SRT captions"""
    # Split by sentences
    sentences = [s.strip() for s in text.replace('।', '.').split('.') if s.strip()]
    time_per_sentence = duration / len(sentences) if sentences else duration
    
    srt_content = ""
    current_time = 0
    
    for i, sentence in enumerate(sentences, 1):
        start_time = format_srt_time(current_time)
        current_time += time_per_sentence
        end_time = format_srt_time(current_time)
        
        srt_content += f"{i}\n{start_time} --> {end_time}\n{sentence}\n\n"
    
    return srt_content

def format_srt_time(seconds):
    """Format seconds to SRT timestamp"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

async def generate_voiceover_with_edge_tts(text, output_path):
    """Generate voiceover using Microsoft Edge TTS with Hindi Male voice (Madhur) at 1.25x speed"""
    print(f"🎙️ Generating voiceover with Edge TTS (hi-IN-MadhurNeural) at 1.25x speed: {text[:50]}...")
    
    # Edge TTS voice: Hindi Male - Madhur
    voice = "hi-IN-MadhurNeural"
    
    # Generate speech with 25% faster rate
    communicate = edge_tts.Communicate(text, voice, rate="+25%")
    
    # Save to file
    await communicate.save(output_path)
    
    print(f"✅ Voiceover generated at 1.25x speed: {output_path}")
    
    # Get actual audio duration using ffprobe
    try:
        import subprocess
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', output_path],
            capture_output=True,
            text=True
        )
        duration = float(result.stdout.strip())
        return output_path, duration
    except Exception as e:
        print(f"⚠️ Could not get duration: {e}, using estimate")
        word_count = len(text.split())
        duration = (word_count / 150) * 60
        return output_path, duration

def generate_voiceover_sync(text, output_path):
    """Synchronous wrapper for async Edge TTS generation"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(generate_voiceover_with_edge_tts(text, output_path))

def upload_to_r2(file_path, remote_key):
    """Upload file to Cloudflare R2"""
    print(f"☁️ Uploading to R2: {remote_key}")
    
    # Get R2 configuration from environment
    r2_endpoint = os.environ.get('R2_ENDPOINT', '').strip()
    r2_access_key = os.environ.get('R2_ACCESS_KEY', '').strip()
    r2_secret_key = os.environ.get('R2_SECRET_KEY', '').strip()
    r2_bucket = os.environ.get('R2_BUCKET', '').strip()
    r2_public_url = os.environ.get('R2_PUBLIC_URL', '').strip()
    
    # Validate configuration
    if not all([r2_endpoint, r2_access_key, r2_secret_key, r2_bucket, r2_public_url]):
        raise Exception("Missing R2 configuration. Check GitHub secrets.")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_access_key,
        aws_secret_access_key=r2_secret_key,
        region_name='auto'
    )
    
    # Determine content type
    if file_path.endswith('.wav'):
        content_type = 'audio/wav'
    elif file_path.endswith('.mp3'):
        content_type = 'audio/mpeg'
    else:
        content_type = 'text/plain'
    
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
    print("🚀 Starting Edge TTS Voiceover Generation (Hindi Male - Madhur)")
    
    # Parse input news data
    news_data = json.loads(os.environ['NEWS_DATA'])
    print(f"📋 Processing {len(news_data)} news items")
    
    results = []
    timestamp = int(os.environ.get('GITHUB_RUN_ID', '0'))
    
    for i, item in enumerate(news_data, 1):
        print(f"\n📰 Processing {i}/{len(news_data)}: {item.get('title', 'Untitled')}")
        
        try:
            text = item.get('fullText', item.get('script', ''))
            number = item.get('number', i)
            
            # Generate voiceover with Edge TTS
            audio_filename = f"voiceover_{number}.mp3"
            audio_path, duration = generate_voiceover_sync(text, audio_filename)
            
            # Generate SRT
            srt_content = generate_srt(text, duration)
            srt_filename = f"caption_{number}.srt"
            with open(srt_filename, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            # Upload to R2
            audio_key = f"voiceovers/edgetts_{timestamp}_{number}.mp3"
            srt_key = f"captions/edgetts_{timestamp}_{number}.srt"
            
            audio_url = upload_to_r2(audio_filename, audio_key)
            srt_url = upload_to_r2(srt_filename, srt_key)
            
            results.append({
                **item,
                'status': 'success',
                'audioUrl': audio_url,
                'srtUrl': srt_url,
                'duration': round(duration),
                'engine': 'edge-tts',
                'voice': 'hi-IN-MadhurNeural'
            })
            
            # Cleanup local files
            os.remove(audio_filename)
            os.remove(srt_filename)
            
        except Exception as e:
            print(f"❌ Error processing item {i}: {e}")
            results.append({
                **item,
                'status': 'failed',
                'error': str(e)
            })
    
    # Save results
    with open('results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Upload results JSON to R2
    try:
        results_key = f"summaries/edgetts_batch_{timestamp}.json"
        results_url = upload_to_r2('results.json', results_key)
        print(f"\n✅ Results uploaded: {results_url}")
    except Exception as e:
        print(f"⚠️ Failed to upload results: {e}")
    
    success_count = sum(1 for r in results if r.get('status') == 'success')
    print(f"\n🎉 Complete! {success_count}/{len(news_data)} successful")

if __name__ == '__main__':
    main()
