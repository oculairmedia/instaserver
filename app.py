import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Mock data for testing
MOCK_MEDIA = [
    {
        "id": "test_media_1",
        "caption": "Test post 1",
        "comments_count": 2,
        "timestamp": "2024-02-04T00:00:00+0000",
        "permalink": "https://instagram.com/p/test1"
    },
    {
        "id": "test_media_2",
        "caption": "Test post 2",
        "comments_count": 1,
        "timestamp": "2024-02-04T00:00:00+0000",
        "permalink": "https://instagram.com/p/test2"
    }
]

MOCK_COMMENTS = {
    "test_media_1": [
        {
            "id": "comment1",
            "text": "Great post!",
            "timestamp": "2024-02-04T01:00:00+0000",
            "username": "user1"
        }
    ],
    "test_media_2": [
        {
            "id": "comment3",
            "text": "Nice!",
            "timestamp": "2024-02-04T03:00:00+0000",
            "username": "user3"
        }
    ]
}

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
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    
    # Send the request
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text[:500]}")  # Show first 500 chars
        
        if response.status_code == 200:
            print("Successfully sent notification to Letta")
            return True
        else:
            print(f"Failed to send notification. Status code: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("Timeout error when sending notification to Letta")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Network error when sending notification to Letta: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error when sending notification to Letta: {e}")
        return False

def get_media_list():
    """Get list of media posts"""
    return MOCK_MEDIA

def get_comments(media_id):
    """Get comments for a specific media post"""
    return MOCK_COMMENTS.get(media_id, [])

@app.route('/')
def index():
    """Main page"""
    try:
        media_list = get_media_list()
        return render_template('index.html', media_list=media_list)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/media/<media_id>/comments')
def media_comments(media_id):
    """Get comments for a media post"""
    comments = get_comments(media_id)
    return jsonify(comments)

@app.route('/media/<media_id>/comment', methods=['POST'])
def post_comment(media_id):
    """Post a new comment and notify Letta"""
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Message is required"}), 400
    
    message = data['message']
    username = data.get('username', 'anonymous')
    
    try:
        # Send notification to Letta
        notify_letta(username, message)
        
        # Create new comment
        new_comment = {
            "id": f"comment_{datetime.now().timestamp()}",
            "text": message,
            "username": username,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to mock data
        if media_id not in MOCK_COMMENTS:
            MOCK_COMMENTS[media_id] = []
        MOCK_COMMENTS[media_id].append(new_comment)
        
        return jsonify({
            "success": True,
            "comment": new_comment
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=52810)