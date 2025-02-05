import os
import hmac
import hashlib
import logging
from flask import Flask, render_template, request, jsonify, abort
from dotenv import load_dotenv
import requests
import json
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Get Instagram account details using Graph API
def get_instagram_account_info():
    try:
        # Get the business account ID and access token from environment
        business_id = os.getenv('BUSINESS_ACCOUNT_ID')
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        
        if not business_id:
            logger.error("BUSINESS_ACCOUNT_ID not set in environment")
            return None
            
        if not access_token:
            logger.error("FACEBOOK_ACCESS_TOKEN not set in environment")
            return None
            
        # Get Instagram Business Account info directly
        account_url = f"https://graph.facebook.com/v19.0/{business_id}"
        account_params = {
            "access_token": access_token,
            "fields": "id,username,name,profile_picture_url"
        }
        
        response = requests.get(account_url, params=account_params)
        
        if response.status_code != 200:
            logger.error(f"Failed to get account info. Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
        return response.json()
        
    except Exception as e:
        logger.error(f"Error getting Instagram account info: {e}")
        logger.error(f"Error type: {type(e)}")
        return None

# Log all environment variables and account info at startup
def log_config():
    logger.info("=== Application Configuration ===")
    env_vars = [
        'INSTAGRAM_APP_ID',
        'APP_SECRET',
        'WEBHOOK_VERIFY_TOKEN',
        'BUSINESS_ACCOUNT_ID',
        'FACEBOOK_ACCESS_TOKEN',
        'PORT'
    ]
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if var in ['APP_SECRET', 'WEBHOOK_VERIFY_TOKEN']:
                masked = value[:4] + '*' * (len(value) - 4)
                logger.info(f"{var}: {masked}")
            else:
                logger.info(f"{var}: {value}")
        else:
            logger.warning(f"{var} not set!")
    
    # Get and log Instagram account info
    logger.info("\n=== Connected Instagram Account ===")
    account_info = get_instagram_account_info()
    if account_info:
        logger.info(f"Account ID: {account_info.get('id')}")
        logger.info(f"Name: {account_info.get('name')}")
        logger.info(f"Username: @{account_info.get('username')}")
        logger.info(f"Profile Picture: {account_info.get('profile_picture_url')}")
    else:
        logger.warning("No Instagram account information available")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Log startup configuration
log_config()

def verify_webhook_signature(request_data, signature_header):
    """Verify that the webhook request came from Instagram"""
    logger.info("=== Webhook Signature Verification ===")
    logger.debug(f"Received signature header: {signature_header}")
    logger.debug(f"Raw request data: {request_data}")
    
    if not signature_header:
        logger.error("No signature header received")
        return False

    # Get the app secret from environment
    app_secret = os.getenv('APP_SECRET')
    if not app_secret:
        logger.error("No APP_SECRET found in environment")
        return False

    # Calculate expected SHA1 signature
    try:
        expected_sha1 = hmac.new(
            app_secret.encode('utf-8'),
            msg=request_data,
            digestmod=hashlib.sha1
        ).hexdigest()
        logger.debug(f"Expected SHA1: sha1={expected_sha1}")
        
        # Compare SHA1 signatures
        if signature_header.startswith('sha1='):
            result = hmac.compare_digest(f"sha1={expected_sha1}", signature_header)
            logger.info(f"SHA1 signature verification result: {result}")
            if result:
                return True
            else:
                logger.warning("SHA1 signatures don't match!")
                logger.warning(f"Expected: sha1={expected_sha1}")
                logger.warning(f"Received: {signature_header}")
    except Exception as e:
        logger.error(f"Error calculating/comparing SHA1 signature: {str(e)}")

    return False

def notify_letta(username, comment):
    """Send a notification to Letta about a new comment"""
    logger.info("=== Sending Letta Notification ===")
    url = "https://letta2.oculair.ca/v1/agents/agent-070e23da-b3db-4f5c-aeb1-f115febf684e/messages/stream"
    logger.debug(f"Notification URL: {url}")
    
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
    
    logger.info(f"Sending notification for comment from @{username}")
    logger.debug(f"Request headers: {json.dumps(headers, indent=2)}")
    logger.debug(f"Request data: {json.dumps(data, indent=2)}")
    
    # Send the request
    try:
        logger.info("Sending request to Letta...")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response body (first 500 chars): {response.text[:500]}")
        
        if response.status_code == 200:
            logger.info("Successfully sent notification to Letta")
            return True
        else:
            logger.error(f"Failed to send notification. Status code: {response.status_code}")
            logger.error(f"Error response: {response.text}")
            return False
    except requests.exceptions.Timeout:
        logger.error("Timeout error when sending notification to Letta")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error when sending notification to Letta: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when sending notification to Letta: {e}")
        logger.error(f"Error type: {type(e)}")
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
    logger.info("=== Received Webhook Request ===")
    logger.info(f"Remote IP: {request.remote_addr}")
    logger.info(f"Request Method: {request.method}")
    logger.info(f"Request Path: {request.path}")
    logger.debug(f"Request Headers: {dict(request.headers)}")
    
    # Get and log raw data
    raw_data = request.get_data()
    logger.debug(f"Raw request data: {raw_data}")
    logger.debug(f"Raw data type: {type(raw_data)}")
    logger.debug(f"Raw data length: {len(raw_data)}")
    
    # Get signatures from headers
    sha1_sig = request.headers.get('X-Hub-Signature')
    sha256_sig = request.headers.get('X-Hub-Signature-256')
    logger.info(f"X-Hub-Signature header: {sha1_sig}")
    logger.info(f"X-Hub-Signature-256 header: {sha256_sig}")
    
    # Try SHA1 signature first
    if sha1_sig and verify_webhook_signature(raw_data, sha1_sig):
        logger.info("SHA1 signature verification successful")
    else:
        logger.error("Signature verification failed - Unauthorized request")
        abort(403)

    # Parse and log JSON data
    try:
        data = request.json
        logger.debug(f"Parsed JSON data: {json.dumps(data, indent=2)}")
    except Exception as e:
        logger.error(f"Failed to parse JSON data: {str(e)}")
        return 'Invalid JSON', 400
    
    try:
        # Handle the webhook
        if data.get('object') == 'instagram':
            logger.info("Processing Instagram webhook")
            for entry in data.get('entry', []):
                logger.debug(f"Processing entry: {json.dumps(entry, indent=2)}")
                for change in entry.get('changes', []):
                    logger.debug(f"Processing change: {json.dumps(change, indent=2)}")
                    if change.get('field') == 'comments':
                        comment_data = change.get('value', {})
                        if comment_data:
                            username = comment_data.get('from', {}).get('username')
                            text = comment_data.get('text')
                            
                            if username and text:
                                logger.info(f"New comment detected from @{username}")
                                logger.info(f"Comment text: {text}")
                                
                                # Send notification to Letta
                                notify_letta(username, text)
                            else:
                                logger.warning("Comment data missing username or text")
                                logger.debug(f"Comment data: {json.dumps(comment_data, indent=2)}")
        else:
            logger.warning(f"Unexpected webhook object type: {data.get('object')}")
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return 'Error', 500

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.getenv('PORT', 54068))  # Using the provided port
    app.run(host='0.0.0.0', port=port)