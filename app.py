import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import threading
import time
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
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print(f"Message: New Instagram comment from @{username}: {comment}")
    
    # Send the request
    try:
        print("\nSending request to Letta...")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text[:500]}")  # First 500 chars
        
        if response.status_code == 200:
            print("Successfully sent notification to Letta")
            return True
        else:
            print(f"Failed to send notification. Status code: {response.status_code}")
            print(f"Error response: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("Timeout error when sending notification to Letta")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Network error when sending notification to Letta: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error when sending notification to Letta: {e}")
        print(f"Error type: {type(e)}")
        return False

def get_instagram_token():
    """Get Instagram API token"""
    try:
        # Get an app access token
        auth_url = "https://graph.facebook.com/oauth/access_token"
        params = {
            "client_id": os.getenv('INSTAGRAM_APP_ID'),
            "client_secret": os.getenv('APP_SECRET'),
            "grant_type": "client_credentials"
        }
        response = requests.get(auth_url, params=params)
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except Exception as e:
        print(f"Error getting Instagram token: {e}")
        return None

def check_for_new_comments():
    """Check for new comments on Instagram posts"""
    global LAST_SEEN_COMMENTS
    
    while True:
        try:
            # Get access token
            access_token = get_instagram_token()
            if not access_token:
                print("Failed to get access token, retrying in 60 seconds...")
                time.sleep(60)
                continue
            
            # Get the business account's media
            url = f"https://graph.facebook.com/v19.0/{os.getenv('BUSINESS_ACCOUNT_ID')}/media"
            params = {
                "access_token": access_token,
                "fields": "id,comments{id,text,username,timestamp}"
            }
            
            print("\nFetching media...")
            response = requests.get(url, params=params)
            
            if response.status_code != 200:
                print(f"Error getting media: {response.text}")
                time.sleep(60)
                continue
                
            media_list = response.json().get('data', [])
            print(f"Found {len(media_list)} posts")
            
            for media in media_list:
                try:
                    media_id = media['id']
                    print(f"\nChecking media {media_id}")
                    
                    # Get comments for this media
                    comments = media.get('comments', {}).get('data', [])
                    print(f"Found {len(comments)} comments")
                    
                    # Initialize if this is the first time seeing this media
                    if media_id not in LAST_SEEN_COMMENTS:
                        print("Initializing comment tracking")
                        LAST_SEEN_COMMENTS[media_id] = {
                            comment['id']: {
                                'timestamp': datetime.fromisoformat(comment['timestamp'].replace('Z', '+00:00')),
                                'text': comment['text'],
                                'username': comment['username']
                            }
                            for comment in comments
                        }
                        continue
                    
                    # Check for new comments
                    for comment in comments:
                        comment_id = comment['id']
                        if comment_id not in LAST_SEEN_COMMENTS[media_id]:
                            comment_timestamp = datetime.fromisoformat(comment['timestamp'].replace('Z', '+00:00'))
                            
                            # Only notify about comments made in the last minute
                            if comment_timestamp > datetime.now(comment_timestamp.tzinfo) - timedelta(minutes=1):
                                print(f"\nNew comment detected!")
                                print(f"Text: {comment['text']}")
                                print(f"By: {comment['username']}")
                                print(f"At: {comment_timestamp}")
                                
                                # Send notification to Letta
                                notify_letta(comment['username'], comment['text'])
                            
                            # Update last seen comments
                            LAST_SEEN_COMMENTS[media_id][comment_id] = {
                                'timestamp': comment_timestamp,
                                'text': comment['text'],
                                'username': comment['username']
                            }
                    
                except Exception as e:
                    print(f"Error processing media {media_id}: {e}")
                    continue
            
        except Exception as e:
            print(f"Error in comment checking loop: {e}")
        
        # Wait before next check
        time.sleep(30)

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