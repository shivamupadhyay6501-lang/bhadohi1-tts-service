#!/usr/bin/env python3
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
    """Generate voiceover using Piper TTS"""
    print(f"🎙️ Generating voiceover: {text[:50]}...")
    
    # Run Piper TTS
    cmd = [
        './piper/piper',
        '--model', 'hi_IN-medium.onnx',
        '--output_file', output_path
    ]
    
    # Pass text via stdin
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = process.communicate(input=text)
    
    if process.returncode != 0:
        raise Exception(f"Piper TTS failed: {stderr}")
    
    print(f"✅ Voiceover generated: {output_path}")
    return output_path

def upload_to_r2(file_path, remote_key):
    """Upload file to Cloudflare R2"""
    print(f"☁️ Uploading to R2: {remote_key}")
    
    s3_client = boto3.client(
        's3',
        endpoint_url=os.environ['R2_ENDPOINT'],
        aws_access_key_id=os.environ['R2_ACCESS_KEY'],
        aws_secret_access_key=os.environ['R2_SECRET_KEY'],
        region_name='auto'
    )
    
    # Determine content type
    content_type = 'audio/wav' if file_path.endswith('.wav') else 'text/plain'
    
    with open(file_path, 'rb') as f:
        s3_client.put_object(
            Bucket=os.environ['R2_BUCKET'],
            Key=remote_key,
            Body=f,
            ContentType=content_type
        )
    
    public_url = f"{os.environ['R2_PUBLIC_URL']}/{remote_key}"
    print(f"✅ Uploaded: {public_url}")
    return public_url

def main():
    print("🚀 Starting Piper TTS Voiceover Generation")
    
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
            audio_path = generate_voiceover_with_piper(text, audio_filename)
            
            # Get audio duration (estimate: 150 words/min)
            word_count = len(text.split())
            duration = (word_count / 150) * 60
            
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
                'engine': 'piper'
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
