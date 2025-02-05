import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
from datetime import datetime
import threading
import time
from instagrapi import Client
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Store last seen comments to detect new ones
LAST_SEEN_COMMENTS = {}

def notify_letta(username, comment):
    """Send a notification to Letta about a new comment"""
    url = "https://letta2.oculair.ca/v1/agents/agent-070e23da-b3db-4f5c-aeb1-f115febf684e/messages/stream"
    
    # Prepare the message data
    data = {
        "messages": [
            {
                "role": "user",
                "content": f"New Instagram comment from @{username}: {comment}"
            }
        ],
        "stream_steps": True,
        "stream_tokens": True
    }
    
    # Set headers
    headers = {
        "X-BARE-PASSWORD": "password lettaSecurePass123",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    print(f"\n=== Sending Letta Notification ===")
    print(f"Message: New Instagram comment from @{username}: {comment}")
    
    # Send the request
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"Letta response status: {response.status_code}")
        if response.status_code == 200:
            print("Successfully sent notification to Letta")
            return True
        else:
            print(f"Failed to send notification. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error sending Letta notification: {e}")
        return False

def check_for_new_comments():
    """Check for new comments on Instagram posts"""
    global LAST_SEEN_COMMENTS
    
    # Initialize Instagram client
    cl = Client()
    try:
        cl.login(os.getenv('INSTAGRAM_USERNAME'), os.getenv('INSTAGRAM_PASSWORD'))
        print("Successfully logged in to Instagram")
    except Exception as e:
        print(f"Failed to login to Instagram: {e}")
        return
    
    while True:
        try:
            # Get user's media
            user_id = cl.user_id
            medias = cl.user_medias(user_id, 20)  # Get last 20 posts
            
            print(f"\nChecking {len(medias)} posts for new comments...")
            
            for media in medias:
                media_id = str(media.id)
                comments = cl.media_comments(media.id)
                current_comments = {
                    str(comment.pk): {
                        'id': str(comment.pk),
                        'text': comment.text,
                        'username': comment.user.username,
                        'timestamp': str(comment.created_at_utc)
                    }
                    for comment in comments
                }
                
                # Initialize if this is the first time seeing this media
                if media_id not in LAST_SEEN_COMMENTS:
                    print(f"Initializing tracking for media {media_id} with {len(current_comments)} comments")
                    LAST_SEEN_COMMENTS[media_id] = current_comments
                    continue
                
                # Check for new comments
                for comment_id, comment in current_comments.items():
                    if comment_id not in LAST_SEEN_COMMENTS[media_id]:
                        print(f"\nNew comment detected!")
                        print(f"Media ID: {media_id}")
                        print(f"Comment: {comment['text']}")
                        print(f"By: {comment['username']}")
                        
                        # Send notification to Letta
                        notify_letta(comment['username'], comment['text'])
                        
                        # Update last seen comments
                        LAST_SEEN_COMMENTS[media_id][comment_id] = comment
            
        except Exception as e:
            print(f"Error in comment checking loop: {e}")
            # Try to login again in case session expired
            try:
                cl.login(os.getenv('INSTAGRAM_USERNAME'), os.getenv('INSTAGRAM_PASSWORD'))
                print("Re-logged in to Instagram")
            except:
                pass
        
        # Wait before next check
        time.sleep(30)  # Check every 30 seconds

@app.route('/')
def index():
    """Main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/debug')
def debug():
    """Debug endpoint"""
    return jsonify({
        'username': os.getenv('INSTAGRAM_USERNAME'),
        'tracked_media': len(LAST_SEEN_COMMENTS),
        'total_comments': sum(len(comments) for comments in LAST_SEEN_COMMENTS.values())
    })

if __name__ == '__main__':
    # Start the comment monitoring thread
    monitor_thread = threading.Thread(target=check_for_new_comments, daemon=True)
    monitor_thread.start()
    print("Started comment monitoring thread")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=52810)