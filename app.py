import os
import hmac
import hashlib
import logging
from flask import Flask, render_template, request, jsonify, abort
from dotenv import load_dotenv
import requests
import json
from datetime import datetime
from collections import OrderedDict

# Cache to store recently processed comment IDs and Instagram account info
PROCESSED_COMMENTS = OrderedDict()
MAX_CACHE_SIZE = 1000  # Maximum number of comment IDs to store
INSTAGRAM_ACCOUNT_ID = None  # Will be set at startup

def add_processed_comment(comment_id):
    """Add a comment ID to the processed cache and maintain size limit"""
    PROCESSED_COMMENTS[comment_id] = datetime.now()
    if len(PROCESSED_COMMENTS) > MAX_CACHE_SIZE:
        # Remove oldest entries when cache gets too big
        while len(PROCESSED_COMMENTS) > MAX_CACHE_SIZE:
            PROCESSED_COMMENTS.popitem(last=False)

def is_comment_processed(comment_id):
    """Check if a comment ID has been processed recently"""
    return comment_id in PROCESSED_COMMENTS

# Set up logging with version info
VERSION = "1.0.0"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.info(f"Starting Instagram Webhook Server v{VERSION}")

# Get Instagram account details using Graph API
def get_instagram_account_info():
    try:
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        
        if not access_token:
            logger.error("FACEBOOK_ACCESS_TOKEN not set in environment")
            return None
            
        # First, get the Facebook Pages
        logger.info("Getting Facebook Pages...")
        pages_url = "https://graph.facebook.com/v19.0/me/accounts"
        pages_params = {
            "access_token": access_token,
            "fields": "id,name,access_token,instagram_business_account{id,username,profile_picture_url}"
        }
        
        logger.debug(f"Requesting Facebook Pages from: {pages_url}")
        logger.debug(f"With parameters: {json.dumps(pages_params, indent=2)}")
        
        pages_response = requests.get(pages_url, params=pages_params)
        
        logger.debug(f"Pages API Response Status: {pages_response.status_code}")
        logger.debug(f"Pages API Response Headers: {dict(pages_response.headers)}")
        logger.debug(f"Pages API Response Body: {pages_response.text}")
        
        if pages_response.status_code != 200:
            logger.error(f"Failed to get pages. Status: {pages_response.status_code}")
            logger.error(f"Response: {pages_response.text}")
            return None
            
        pages_data = pages_response.json()
        logger.debug(f"Pages response: {json.dumps(pages_data, indent=2)}")
        
        # Look for the page with an Instagram Business Account
        for page in pages_data.get('data', []):
            if 'instagram_business_account' in page:
                insta_account = page['instagram_business_account']
                logger.info(f"Found Instagram Business Account in page: {page['name']}")
                # Store the Instagram account ID globally
                global INSTAGRAM_ACCOUNT_ID
                INSTAGRAM_ACCOUNT_ID = insta_account['id']
                
                return {
                    'id': insta_account['id'],
                    'username': insta_account['username'],
                    'name': page['name'],
                    'profile_picture_url': insta_account.get('profile_picture_url'),
                    'page_id': page['id'],
                    'page_access_token': page['access_token']
                }
        
        logger.error("No Instagram Business Account found in any Facebook Page")
        return None
        
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

# Initialize Flask app
load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global variables for account info
instagram_account = None
page_access_token = None
page_id = None

def init_once():
    """Initialize things that should only happen once"""
    global instagram_account, page_access_token, page_id
    
    # Only initialize if not already done
    if instagram_account is None:
        log_config()
        account_info = get_instagram_account_info()
        
        if account_info:
            instagram_account = account_info
            page_access_token = account_info.get('page_access_token')
            page_id = account_info.get('page_id')
            
            logger.info(f"Account ID: {account_info.get('id')}")
            logger.info(f"Name: {account_info.get('name')}")
            logger.info(f"Username: @{account_info.get('username')}")
            logger.info(f"Profile Picture: {account_info.get('profile_picture_url')}")
            logger.info(f"Page ID: {page_id}")
            logger.debug(f"Page Access Token: {page_access_token[:10]}...")
        else:
            logger.warning("No Instagram account information available")

# Enable webhook subscriptions
def enable_webhook_subscriptions():
    """Enable webhook subscriptions for the Instagram account"""
    try:
        global instagram_account
        
        app_id = os.getenv('INSTAGRAM_APP_ID')
        app_secret = os.getenv('APP_SECRET')
        
        if not app_id or not app_secret or not instagram_account:
            logger.error("Missing required credentials")
            return False
            
        # Generate app access token
        app_access_token = f"{app_id}|{app_secret}"
            
        # Subscribe to Instagram comments and mentions
        insta_url = f"https://graph.facebook.com/v19.0/{instagram_account['id']}/subscribed_apps"
        insta_params = {
            "access_token": app_access_token,
            "subscribed_fields": "comments,mentions"
        }
        
        logger.info("Subscribing to Instagram webhooks...")
        logger.debug(f"Using URL: {insta_url}")
        logger.debug(f"Using fields: {insta_params['subscribed_fields']}")
        
        response = requests.post(insta_url, params=insta_params)
        
        if response.status_code == 200:
            logger.info("Successfully enabled webhook subscriptions")
            return True
        else:
            logger.error(f"Failed to subscribe to webhooks: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error enabling subscriptions: {e}")
        logger.error(f"Error type: {type(e)}")
        return False

# Initialize on module load (will only happen once)
def initialize_app():
    """Initialize the application and enable webhooks"""
    init_once()
    
    if page_access_token and page_id:
        logger.info(f"Using page ID: {page_id}")
        logger.info("Attempting to enable webhook subscriptions...")
        if enable_webhook_subscriptions():
            logger.info("Webhook subscriptions enabled successfully")
        else:
            logger.error("Failed to enable webhook subscriptions")
    else:
        logger.error("Missing page access token or page ID - cannot enable webhooks")

initialize_app()

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
    message = f"New Instagram comment from @{username}: {comment}"
    data = {
        "messages": [
            {
                "role": "user",
                "content": message
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
    logger.info(f"Message content: {message}")
    logger.debug(f"Request headers: {json.dumps(headers, indent=2)}")
    logger.debug(f"Request data: {json.dumps(data, indent=2)}")
    
    # Send the request
    try:
        logger.info("Sending request to Letta...")
        start_time = datetime.now()
        
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Request took {duration:.2f} seconds")
        
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        # Log full response for debugging
        logger.debug("Full response body:")
        logger.debug(response.text)
        
        if response.status_code == 200:
            logger.info("Successfully sent notification to Letta")
            # Try to parse the response to verify Letta received it
            try:
                events = response.text.strip().split('\n\n')
                for event in events:
                    if event.startswith('data: '):
                        event_data = json.loads(event[6:])  # Skip 'data: ' prefix
                        logger.info(f"Letta event: {json.dumps(event_data, indent=2)}")
            except Exception as e:
                logger.warning(f"Could not parse Letta response events: {e}")
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
        logger.error(f"Full error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when sending notification to Letta: {e}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Full error: {str(e)}")
        return False

# Store API responses and webhook history
api_responses = {
    'pages': None,
    'page_subscription': None,
    'instagram_subscription': None
}
recent_webhooks = []
MAX_WEBHOOKS = 10

@app.route('/')
def index():
    """Main page"""
    try:
        # Get environment variables (masked)
        env_vars = {
            'INSTAGRAM_APP_ID': os.getenv('INSTAGRAM_APP_ID'),
            'APP_SECRET': os.getenv('APP_SECRET'),
            'WEBHOOK_VERIFY_TOKEN': os.getenv('WEBHOOK_VERIFY_TOKEN'),
            'FACEBOOK_ACCESS_TOKEN': os.getenv('FACEBOOK_ACCESS_TOKEN')
        }
        
        return render_template(
            'index.html',
            instagram_account=instagram_account or {},
            env=env_vars,
            api_responses=api_responses,
            recent_webhooks=recent_webhooks
        )
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 500

@app.route('/debug/test-webhook', methods=['POST'])
def test_webhook():
    """Send a test webhook"""
    try:
        test_data = {
            "entry": [{
                "id": "0",
                "time": int(datetime.now().timestamp()),
                "changes": [{
                    "field": "comments",
                    "value": {
                        "from": {
                            "id": "test_user_id",
                            "username": "test_user"
                        },
                        "text": "This is a test comment",
                        "id": f"test_{int(datetime.now().timestamp())}",
                        "media": {
                            "id": instagram_account['id'] if instagram_account else "test_media_id"
                        }
                    }
                }]
            }],
            "object": "instagram"
        }
        
        # Process the test webhook
        webhook_handle_internal(test_data, is_test=True)
        
        return jsonify({"success": True, "message": "Test webhook processed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/debug/refresh-subscriptions', methods=['POST'])
def refresh_subscriptions():
    """Refresh webhook subscriptions"""
    try:
        if enable_webhook_subscriptions():
            return jsonify({"success": True, "message": "Subscriptions refreshed"})
        else:
            return jsonify({"success": False, "error": "Failed to refresh subscriptions"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/debug/clear-history', methods=['POST'])
def clear_history():
    """Clear webhook history"""
    try:
        global recent_webhooks
        recent_webhooks = []
        return jsonify({"success": True, "message": "History cleared"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """Handle the webhook verification from Instagram"""
    logger.info("=== Webhook Verification Request ===")
    logger.info(f"Remote IP: {request.remote_addr}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Args: {dict(request.args)}")
    
    # Verify token should match what you set in the Instagram app
    VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN', 'your_verify_token')
    logger.info(f"Our verify token: {VERIFY_TOKEN}")
    
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    logger.info(f"Mode: {mode}")
    logger.info(f"Token: {token}")
    logger.info(f"Challenge: {challenge}")

    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully!")
            return challenge
        else:
            logger.error(f"Verification failed. Mode: {mode}, Token match: {token == VERIFY_TOKEN}")
            abort(403)
    
    logger.error("Missing mode or token")
    abort(400)

@app.route('/webhook', methods=['POST'])
def webhook_handle():
    """Handle incoming webhooks from Instagram"""
    logger.info("\n=== Received Webhook Request ===")
    logger.info(f"Remote IP: {request.remote_addr}")
    logger.info(f"Request Method: {request.method}")
    logger.info(f"Request Path: {request.path}")
    logger.info(f"Request Headers: {dict(request.headers)}")
    
    # Get and log raw data
    raw_data = request.get_data()
    logger.info(f"Raw request data: {raw_data}")
    logger.info(f"Raw data type: {type(raw_data)}")
    logger.info(f"Raw data length: {len(raw_data)}")
    
    # Get signatures from headers
    sha1_sig = request.headers.get('X-Hub-Signature')
    sha256_sig = request.headers.get('X-Hub-Signature-256')
    logger.info(f"X-Hub-Signature header: {sha1_sig}")
    logger.info(f"X-Hub-Signature-256 header: {sha256_sig}")
    
    # Try SHA1 signature first
    signature_valid = False
    if sha1_sig and verify_webhook_signature(raw_data, sha1_sig):
        logger.info("SHA1 signature verification successful")
        signature_valid = True
    else:
        logger.error("Signature verification failed")
        logger.error(f"APP_SECRET length: {len(os.getenv('APP_SECRET', ''))}")
        logger.error(f"Expected signature format: sha1=HASH")
        abort(403)

    # Parse and log JSON data
    try:
        data = request.json
        return webhook_handle_internal(data, signature_valid)
    except Exception as e:
        logger.error(f"Failed to parse JSON data: {str(e)}")
        return 'Invalid JSON', 400

def webhook_handle_internal(data, signature_valid=True, is_test=False):
    """Internal webhook handling logic"""
    try:
        logger.debug(f"Parsed JSON data: {json.dumps(data, indent=2)}")
        
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
                                comment_id = comment_data.get('id')
                                media_id = comment_data.get('media', {}).get('id')
                                
                                if not comment_id:
                                    logger.warning("Comment data missing ID")
                                    continue
                                    
                                if not is_test and is_comment_processed(comment_id):
                                    logger.info(f"Skipping already processed comment {comment_id}")
                                    continue
                                    
                                logger.info(f"New comment detected from @{username}")
                                logger.info(f"Comment text: {text}")
                                logger.info(f"Comment ID: {comment_id}")
                                
                                # Add to recent webhooks
                                webhook_entry = {
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'signature_valid': signature_valid,
                                    'username': username,
                                    'text': text,
                                    'raw_data': data
                                }
                                recent_webhooks.insert(0, webhook_entry)
                                if len(recent_webhooks) > MAX_WEBHOOKS:
                                    recent_webhooks.pop()
                                
                                # Send notification to Letta
                                if notify_letta(username, text):
                                    # Only mark as processed if notification was successful
                                    if not is_test:
                                        add_processed_comment(comment_id)
                                        logger.info(f"Marked comment {comment_id} as processed")
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