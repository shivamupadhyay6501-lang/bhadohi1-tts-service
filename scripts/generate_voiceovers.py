import os
import json
import subprocess
import boto3
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

def generate_voiceover_with_piper(text, output_path):
    """Generate voiceover using Piper TTS with best Hindi Male voice at normal 1x speed"""
    print(f"🎙️ Generating voiceover with Piper (hi_IN-pratham-medium) at 1x speed: {text[:50]}...")
    
    # Full path to model file (Piper needs absolute path, not just model name)
    home_dir = os.path.expanduser("~")
    voice_model_path = f"{home_dir}/.local/share/piper/voices/hi_IN-pratham-medium.onnx"
    
    # Verify model exists
    if not os.path.exists(voice_model_path):
        raise Exception(f"Model file not found at: {voice_model_path}")
    
    # Run Piper TTS using stdin pipe (safer than temp file for Hindi text)
    cmd = [
        'piper',
        '--model', voice_model_path,
        '--output_file', output_path
    ]
    
    try:
        # Use stdin pipe to pass text directly (avoids file encoding issues)
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        stdout, stderr = process.communicate(input=text.strip())
        
        if process.returncode != 0:
            raise Exception(f"Piper Core Runtime Error: {stderr}")
        
        print(f"✅ Voiceover generated at 1x speed: {output_path}")
        
        # Get actual audio duration using ffprobe
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', output_path],
            capture_output=True,
            text=True
        )
        duration = float(result.stdout.strip())
        
        return output_path, duration
        
    except Exception as e:
        print(f"❌ Piper TTS failed: {e}")
        raise

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
    print("🚀 Starting Piper TTS Voiceover Generation (Hindi Male - Best Quality)")
    
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
            
            # Generate voiceover with Piper
            audio_filename = f"voiceover_{number}.wav"
            audio_path, duration = generate_voiceover_with_piper(text, audio_filename)
            
            # Generate SRT
            srt_content = generate_srt(text, duration)
            srt_filename = f"caption_{number}.srt"
            with open(srt_filename, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            # Upload to R2
            audio_key = f"voiceovers/piper_{timestamp}_{number}.wav"
            srt_key = f"captions/piper_{timestamp}_{number}.srt"
            
            audio_url = upload_to_r2(audio_filename, audio_key)
            srt_url = upload_to_r2(srt_filename, srt_key)
            
            results.append({
                **item,
                'status': 'success',
                'audioUrl': audio_url,
                'srtUrl': srt_url,
                'duration': round(duration),
                'engine': 'piper',
                'voice': 'hi_IN-pratham-medium',
                'speed': '1x'
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
        results_key = f"summaries/piper_batch_{timestamp}.json"
        results_url = upload_to_r2('results.json', results_key)
        print(f"\n✅ Results uploaded: {results_url}")
    except Exception as e:
        print(f"⚠️ Failed to upload results: {e}")
    
    success_count = sum(1 for r in results if r.get('status') == 'success')
    print(f"\n🎉 Complete! {success_count}/{len(news_data)} successful")

if __name__ == '__main__':
    main()
