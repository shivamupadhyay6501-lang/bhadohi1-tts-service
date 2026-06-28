import os
import json
import subprocess
import boto3
from pathlib import Path
from kokoro_onnx import Kokoro
import soundfile as sf
import numpy as np

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

def generate_voiceover_with_kokoro(text, output_path):
    """Generate voiceover using Kokoro Multilingual with Hindi voice at 1.25x speed"""
    print(f"🎙️ Generating voiceover with Kokoro Multilingual (Hindi) at 1.25x speed: {text[:50]}...")
    
    # Initialize Kokoro with multilingual model and voices
    model_path = "kokoro-v1.0.onnx"
    voices_path = "voices-v1.0.bin"
    
    if not os.path.exists(model_path):
        raise Exception(f"❌ Kokoro multilingual model not found: {model_path}")
    if not os.path.exists(voices_path):
        raise Exception(f"❌ Multilingual voices file not found: {voices_path}")
    
    # Create Kokoro instance with multilingual voices
    kokoro = Kokoro(model_path, voices_path)
    
    # Generate audio with Hindi female voice (hf_alpha) at 1.25x speed
    samples, sample_rate = kokoro.create(
        text=text, 
        voice="hf_alpha",  # Hindi Female Alpha voice from multilingual pack
        speed=1.25,
        lang='hi'
    )
    
    # Save to WAV file (kokoro-onnx returns numpy array directly)
    sf.write(output_path, samples, sample_rate)
    
    print(f"✅ Voiceover generated at 1.25x speed: {output_path}")
    return output_path

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
    content_type = 'audio/wav' if file_path.endswith('.wav') else 'text/plain'
    
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
    print("🚀 Starting Kokoro TTS Voiceover Generation")
    
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
            
            # Generate voiceover
            audio_filename = f"voiceover_{number}.wav"
            audio_path = generate_voiceover_with_kokoro(text, audio_filename)
            
            # Get audio duration (estimate: 150 words/min)
            word_count = len(text.split())
            duration = (word_count / 150) * 60
            
            # Generate SRT
            srt_content = generate_srt(text, duration)
            srt_filename = f"caption_{number}.srt"
            with open(srt_filename, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            # Upload to R2
            audio_key = f"voiceovers/kokoro_{timestamp}_{number}.wav"
            srt_key = f"captions/kokoro_{timestamp}_{number}.srt"
            
            audio_url = upload_to_r2(audio_filename, audio_key)
            srt_url = upload_to_r2(srt_filename, srt_key)
            
            results.append({
                **item,
                'status': 'success',
                'audioUrl': audio_url,
                'srtUrl': srt_url,
                'duration': round(duration),
                'engine': 'kokoro',
                'voice': 'hm-psi'
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
        results_key = f"summaries/kokoro_batch_{timestamp}.json"
        results_url = upload_to_r2('results.json', results_key)
        print(f"\n✅ Results uploaded: {results_url}")
    except Exception as e:
        print(f"⚠️ Failed to upload results: {e}")
    
    success_count = sum(1 for r in results if r.get('status') == 'success')
    print(f"\n🎉 Complete! {success_count}/{len(news_data)} successful")

if __name__ == '__main__':
    main()
