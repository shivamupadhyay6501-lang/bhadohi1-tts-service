#!/usr/bin/env python3
"""
Save news reels metadata to Firebase Firestore
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

def init_firebase():
    """Initialize Firebase Admin SDK"""
    if not firebase_admin._apps:
        # Get credentials from environment
        project_id = os.environ.get('FIREBASE_PROJECT_ID')
        private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
        client_email = os.environ.get('FIREBASE_CLIENT_EMAIL')
        
        if not all([project_id, private_key, client_email]):
            raise ValueError("Missing Firebase credentials in environment")
        
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def save_reel_to_firestore(reel_data, news_item):
    """Save individual reel to Firestore"""
    db = init_firebase()
    
    # Prepare document data
    doc_data = {
        'title': news_item['title'],
        'category': news_item.get('category', 'समाचार'),
        'script': news_item.get('script', ''),
        'location': news_item.get('location', 'भदोही'),
        'keywords': news_item.get('keywords', []),
        'importance': news_item.get('importance', 'medium'),
        'video_url': reel_data['reelUrl'],
        'audio_url': news_item.get('voiceoverUrl', ''),
        'thumbnail_url': reel_data.get('thumbnailUrl', reel_data['reelUrl']),  # Use generated thumbnail
        'type': 'short',
        'duration': news_item.get('duration', '0:45'),
        'source': 'Bhadohi1',
        'created_at': firestore.SERVER_TIMESTAMP,
        'views': 0,
        'likes': 0,
        'shares': 0,
    }
    
    # Add document to Firestore
    doc_ref = db.collection('news').add(doc_data)
    doc_id = doc_ref[1].id
    
    print(f"  ✅ Saved to Firestore: {doc_id}")
    return doc_id

def main():
    print("💾 SAVING REELS TO FIRESTORE\n")
    
    # Load reel results
    with open('reel_results.json', 'r', encoding='utf-8') as f:
        reel_results = json.load(f)
    
    # Load original news data
    news_data = json.loads(os.environ['NEWS_DATA'])
    
    print(f"📊 Total reels to save: {len(reel_results['reels'])}\n")
    
    saved_count = 0
    failed_count = 0
    
    for reel in reel_results['reels']:
        if reel.get('status') != 'success':
            print(f"⏭️ Skipping failed reel #{reel['number']}")
            failed_count += 1
            continue
        
        # Find corresponding news item
        news_item = next((item for item in news_data if item['number'] == reel['number']), None)
        
        if not news_item:
            print(f"⚠️ News item not found for reel #{reel['number']}")
            failed_count += 1
            continue
        
        try:
            print(f"📰 Saving reel #{reel['number']}: {reel['title']}")
            doc_id = save_reel_to_firestore(reel, news_item)
            saved_count += 1
        except Exception as e:
            print(f"❌ Error saving reel #{reel['number']}: {e}")
            failed_count += 1
    
    print(f"\n{'='*60}")
    print(f"💾 FIRESTORE SAVE COMPLETE!")
    print(f"{'='*60}")
    print(f"✅ Saved: {saved_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"{'='*60}\n")
    
    # Save summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_reels': len(reel_results['reels']),
        'saved_to_firestore': saved_count,
        'failed': failed_count
    }
    
    with open('firestore_save_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
