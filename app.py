import os
import hmac
import hashlib
from flask import Flask, render_template, request, jsonify, abort
from dotenv import load_dotenv
import requests
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

def verify_webhook_signature(request_data, signature_header):
    """Verify that the webhook request came from Instagram"""
    print("\n=== Webhook Signature Verification ===")
    print(f"Received signature header: {signature_header}")
    
    if not signature_header:
        print("No signature header received")
        return False

    # Get the app secret from environment
    app_secret = os.getenv('APP_SECRET')
    if not app_secret:
        print("No APP_SECRET found in environment")
        return False

    # Calculate expected signature
    expected_signature = hmac.new(
        app_secret.encode('utf-8'),
        msg=request_data,
        digestmod=hashlib.sha256
    ).hexdigest()

    print(f"Expected signature: sha256={expected_signature}")
    
    # Compare signatures
    result = hmac.compare_digest(f"sha256={expected_signature}", signature_header)
    print(f"Signature verification result: {result}")
    return result

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

@app.route('/')
def index():
    """Main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """Handle the webhook verification from Instagram"""
    # Verify token should match what you set in the Instagram app
    VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN', 'your_verify_token')
    
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified!")
            return challenge
        else:
            abort(403)
    
    abort(400)

@app.route('/webhook', methods=['POST'])
def webhook_handle():
    """Handle incoming webhooks from Instagram"""
    print("\n=== Received Webhook Request ===")
    print(f"Headers: {dict(request.headers)}")
    print(f"Raw data: {request.get_data()}")
    
    # Verify the request signature
    signature = request.headers.get('X-Hub-Signature')
    if not verify_webhook_signature(request.get_data(), signature):
        print("Signature verification failed")
        abort(403)

    data = request.json
    print(f"JSON data: {json.dumps(data, indent=2)}")
    
    try:
        # Handle the webhook
        if data.get('object') == 'instagram':
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    if change.get('field') == 'comments':
                        comment_data = change.get('value', {})
                        if comment_data:
                            username = comment_data.get('from', {}).get('username')
                            text = comment_data.get('text')
                            
                            if username and text:
                                print(f"\nNew comment from webhook!")
                                print(f"Text: {text}")
                                print(f"By: {username}")
                                
                                # Send notification to Letta
                                notify_letta(username, text)
        
        return 'OK', 200
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return 'Error', 500

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.getenv('PORT', 54068))  # Using the provided port
    app.run(host='0.0.0.0', port=port)