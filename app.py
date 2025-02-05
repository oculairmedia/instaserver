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

def check_for_new_comments():
    """Check for new comments on Instagram posts"""
    global LAST_SEEN_COMMENTS
    
    # Initialize Instagram client
    cl = None
    login_attempts = 0
    max_login_attempts = 3
    
    def ensure_login():
        nonlocal cl, login_attempts
        if cl is None or login_attempts >= max_login_attempts:
            cl = Client()
            login_attempts = 0
        
        try:
            if not cl.user_id:
                cl.login(os.getenv('INSTAGRAM_USERNAME'), os.getenv('INSTAGRAM_PASSWORD'))
                print("Successfully logged in to Instagram")
                login_attempts = 0
            return True
        except Exception as e:
            print(f"Login attempt failed: {e}")
            login_attempts += 1
            if login_attempts >= max_login_attempts:
                print("Max login attempts reached, waiting 5 minutes...")
                time.sleep(300)  # Wait 5 minutes before trying again
                login_attempts = 0
            return False
    
    while True:
        try:
            if not ensure_login():
                time.sleep(30)
                continue
                
            # Get user's media
            user_id = cl.user_id
            medias = cl.user_medias(user_id, 20)  # Get last 20 posts
            
            print(f"\nChecking {len(medias)} posts for new comments...")
            
            for media in medias:
                try:
                    media_id = str(media.id)
                    print(f"\nChecking media {media_id}")
                    
                    try:
                        comments = cl.media_comments(media.id)
                    except Exception as e:
                        print(f"Error getting comments for media {media_id}: {e}")
                        continue
                        
                    current_comments = {}
                    for comment in comments:
                        try:
                            current_comments[str(comment.pk)] = {
                                'id': str(comment.pk),
                                'text': comment.text,
                                'username': comment.user.username,
                                'timestamp': str(comment.created_at_utc)
                            }
                        except Exception as e:
                            print(f"Error processing comment: {e}")
                            continue
                    
                    # Initialize if this is the first time seeing this media
                    if media_id not in LAST_SEEN_COMMENTS:
                        print(f"Initializing tracking for media {media_id}")
                        print(f"Found {len(current_comments)} comments:")
                        # Store initial comments with their timestamps
                        LAST_SEEN_COMMENTS[media_id] = {
                            comment_id: {
                                'timestamp': datetime.fromisoformat(comment['timestamp']),
                                'text': comment['text'],
                                'username': comment['username']
                            }
                            for comment_id, comment in current_comments.items()
                        }
                        continue
                    
                    # Check for new comments
                    for comment_id, comment in current_comments.items():
                        comment_timestamp = datetime.fromisoformat(comment['timestamp'])
                        
                        # Check if this is a new comment
                        if comment_id not in LAST_SEEN_COMMENTS[media_id]:
                            # Only notify about comments made after server start
                            if comment_timestamp > datetime.now(comment_timestamp.tzinfo) - timedelta(minutes=1):
                                print(f"\nNew comment detected!")
                                print(f"Media ID: {media_id}")
                                print(f"Comment: {comment['text']}")
                                print(f"By: {comment['username']}")
                                print(f"At: {comment_timestamp}")
                                
                                # Send notification to Letta
                                notify_letta(comment['username'], comment['text'])
                            else:
                                print(f"Found existing comment: {comment['text']} by {comment['username']} at {comment_timestamp}")
                            
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
            time.sleep(30)  # Wait before retrying
            continue
        
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

@app.route('/test/comment', methods=['POST'])
def test_comment():
    """Test endpoint to post a comment"""
    try:
        data = request.get_json()
        if not data or 'media_id' not in data or 'text' not in data:
            return jsonify({
                "error": "Required fields: media_id, text"
            }), 400

        media_id = data['media_id']
        text = data['text']

        # Initialize Instagram client
        cl = Client()
        cl.login(os.getenv('INSTAGRAM_USERNAME'), os.getenv('INSTAGRAM_PASSWORD'))
        print(f"Logged in to Instagram as {os.getenv('INSTAGRAM_USERNAME')}")

        # Post the comment
        print(f"Posting comment on media {media_id}")
        print(f"Comment text: {text}")
        
        result = cl.media_comment(
            media_id=media_id,
            text=text
        )
        
        print("Comment posted successfully:", result)
        
        return jsonify({
            "success": True,
            "comment": {
                "id": str(result.pk),
                "text": result.text,
                "username": result.user.username,
                "timestamp": str(result.created_at_utc)
            }
        })

    except Exception as e:
        print(f"Error posting comment: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test/reply', methods=['POST'])
def test_reply():
    """Test endpoint to reply to a comment"""
    try:
        data = request.get_json()
        if not data or 'media_id' not in data or 'comment_id' not in data or 'reply_text' not in data:
            return jsonify({
                "error": "Required fields: media_id, comment_id, reply_text"
            }), 400

        media_id = data['media_id']
        comment_id = data['comment_id']
        reply_text = data['reply_text']

        # Initialize Instagram client
        cl = Client()
        cl.login(os.getenv('INSTAGRAM_USERNAME'), os.getenv('INSTAGRAM_PASSWORD'))
        print(f"Logged in to Instagram as {os.getenv('INSTAGRAM_USERNAME')}")

        # Reply to the comment
        print(f"Replying to comment {comment_id} on media {media_id}")
        print(f"Reply text: {reply_text}")
        
        result = cl.media_comment(
            media_id=media_id,
            text=reply_text,
            replied_to_comment_id=comment_id
        )
        
        print("Reply posted successfully:", result)
        
        return jsonify({
            "success": True,
            "reply": {
                "id": str(result.pk),
                "text": result.text,
                "username": result.user.username,
                "timestamp": str(result.created_at_utc)
            }
        })

    except Exception as e:
        print(f"Error replying to comment: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start the comment monitoring thread
    monitor_thread = threading.Thread(target=check_for_new_comments, daemon=True)
    monitor_thread.start()
    print("Started comment monitoring thread")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=52810)