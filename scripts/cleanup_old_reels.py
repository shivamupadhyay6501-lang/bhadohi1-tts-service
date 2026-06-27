#!/usr/bin/env python3
"""
Cleanup Old Reels - Delete previous workflow reels from R2 and Firestore
Keep only the latest batch (current workflow)
"""

import os
import json
import boto3
from firebase_admin import credentials, firestore, initialize_app

def delete_from_r2(keys_to_delete):
    """Delete files from R2"""
    if not keys_to_delete:
        print("  No files to delete from R2")
        return
    
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
    
    print(f"🗑️  Deleting {len(keys_to_delete)} files from R2...")
    
    # Delete in batches of 1000 (R2 limit)
    for i in range(0, len(keys_to_delete), 1000):
        batch = keys_to_delete[i:i+1000]
        objects = [{'Key': key} for key in batch]
        
        response = s3_client.delete_objects(
            Bucket=r2_bucket,
            Delete={'Objects': objects}
        )
        
        deleted_count = len(response.get('Deleted', []))
        print(f"  ✅ Deleted batch: {deleted_count} files")
    
    print(f"✅ Total deleted from R2: {len(keys_to_delete)} files\n")

def list_r2_objects(prefix):
    """List all objects in R2 with given prefix"""
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
    
    objects = []
    continuation_token = None
    
    while True:
        if continuation_token:
            response = s3_client.list_objects_v2(
                Bucket=r2_bucket,
                Prefix=prefix,
                ContinuationToken=continuation_token
            )
        else:
            response = s3_client.list_objects_v2(
                Bucket=r2_bucket,
                Prefix=prefix
            )
        
        if 'Contents' in response:
            objects.extend([obj['Key'] for obj in response['Contents']])
        
        if response.get('IsTruncated'):
            continuation_token = response.get('NextContinuationToken')
        else:
            break
    
    return objects

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    project_id = os.environ.get('FIREBASE_PROJECT_ID')
    client_email = os.environ.get('FIREBASE_CLIENT_EMAIL')
    private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
    
    cred_dict = {
        "type": "service_account",
        "project_id": project_id,
        "private_key": private_key,
        "client_email": client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    
    cred = credentials.Certificate(cred_dict)
    initialize_app(cred)
    
    return firestore.client()

def delete_old_firestore_reels(db, current_batch_id):
    """Delete old reels from Firestore (keep only current batch)"""
    print(f"🔍 Finding old reels in Firestore (batch != {current_batch_id})...")
    
    # Query all news documents
    news_ref = db.collection('news')
    docs = news_ref.where('type', '==', 'short').stream()
    
    deleted_count = 0
    
    for doc in docs:
        data = doc.to_dict()
        video_url = data.get('video_url', '')
        
        # Check if video URL belongs to current batch
        if f'_{current_batch_id}_' not in video_url:
            # Old reel, delete it
            doc.reference.delete()
            deleted_count += 1
            print(f"  🗑️  Deleted: {data.get('title', 'Unknown')[:50]}...")
    
    print(f"✅ Deleted {deleted_count} old reels from Firestore\n")
    return deleted_count

def main():
    print("🧹 CLEANUP OLD REELS - STARTING\n")
    
    current_batch_id = str(os.environ.get('GITHUB_RUN_ID', '0'))
    print(f"📊 Current batch ID: {current_batch_id}\n")
    
    # Step 1: List all reels in R2
    print("📋 Step 1: Finding old reels in R2...")
    all_reel_keys = list_r2_objects('reels/')
    all_thumb_keys = list_r2_objects('thumbnails/')
    all_voice_keys = list_r2_objects('voiceovers/')
    
    print(f"  Found {len(all_reel_keys)} reels")
    print(f"  Found {len(all_thumb_keys)} thumbnails")
    print(f"  Found {len(all_voice_keys)} voiceovers\n")
    
    # Step 2: Filter old files (not from current batch)
    print(f"📋 Step 2: Identifying files from old batches...")
    
    old_reels = [k for k in all_reel_keys if f'_{current_batch_id}_' not in k]
    old_thumbs = [k for k in all_thumb_keys if f'_{current_batch_id}_' not in k]
    old_voices = [k for k in all_voice_keys if f'_{current_batch_id}_' not in k]
    
    print(f"  Old reels to delete: {len(old_reels)}")
    print(f"  Old thumbnails to delete: {len(old_thumbs)}")
    print(f"  Old voiceovers to delete: {len(old_voices)}\n")
    
    total_old_files = len(old_reels) + len(old_thumbs) + len(old_voices)
    
    if total_old_files == 0:
        print("✅ No old files found! R2 is clean.\n")
    else:
        # Step 3: Delete from R2
        print(f"📋 Step 3: Deleting {total_old_files} old files from R2...")
        all_old_keys = old_reels + old_thumbs + old_voices
        delete_from_r2(all_old_keys)
    
    # Step 4: Delete from Firestore
    print(f"📋 Step 4: Deleting old reels from Firestore...")
    db = initialize_firebase()
    deleted_firestore = delete_old_firestore_reels(db, current_batch_id)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"🎊 CLEANUP COMPLETE!")
    print(f"{'='*70}")
    print(f"🗑️  R2 files deleted: {total_old_files}")
    print(f"🗑️  Firestore reels deleted: {deleted_firestore}")
    print(f"✅ Only latest batch ({current_batch_id}) remains!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
