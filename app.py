import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

INSTAGRAM_APP_ID = os.getenv('INSTAGRAM_APP_ID')
APP_SECRET = os.getenv('APP_SECRET')
BUSINESS_ACCOUNT_ID = os.getenv('BUSINESS_ACCOUNT_ID')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

# For this example, we'll use a system to generate a user access token
# In a production environment, you would use OAuth 2.0 flow
def get_instagram_token():
    try:
        # First get an app access token
        auth_url = "https://graph.facebook.com/oauth/access_token"
        params = {
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": APP_SECRET,
            "grant_type": "client_credentials"
        }
        response = requests.get(auth_url, params=params)
        
        if response.status_code != 200:
            print(f"Error getting app token: {response.text}")
            return None
            
        app_token = response.json().get('access_token')
        
        # Now use the app token to get a page access token
        page_token_url = f"https://graph.facebook.com/v19.0/{BUSINESS_ACCOUNT_ID}"
        page_params = {
            "fields": "access_token",
            "access_token": app_token
        }
        response = requests.get(page_token_url, params=page_params)
        
        if response.status_code == 200:
            return response.json().get('access_token')
        print(f"Error getting page token: {response.text}")
        return None
    except Exception as e:
        print(f"Error getting Instagram token: {e}")
        return None

# Get the access token
ACCESS_TOKEN = get_instagram_token()

def get_long_lived_access_token(short_lived_token):
    url = f"https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": INSTAGRAM_APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_lived_token
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()["access_token"]
    return None

def get_media_list():
    url = f"https://graph.facebook.com/v19.0/{BUSINESS_ACCOUNT_ID}/media"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,caption,comments_count,timestamp,permalink"
    }
    try:
        response = requests.get(url, params=params)
        print(f"Media list response: {response.text}")
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception as e:
        print(f"Error getting media list: {e}")
        return []

def get_comments(media_id):
    url = f"https://graph.facebook.com/v19.0/{media_id}/comments"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,text,timestamp,username,replies{id,text,timestamp,username}"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()["data"]
    return []

def reply_to_comment(comment_id, message):
    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    data = {
        "access_token": ACCESS_TOKEN,
        "message": message
    }
    response = requests.post(url, data=data)
    return response.status_code == 200, response.json()

@app.route('/')
def index():
    if not ACCESS_TOKEN:
        return "Error: Could not obtain access token. Check your credentials.", 500
    
    try:
        media_list = get_media_list()
        if not media_list:
            return "Error: Could not fetch media list. Check your BUSINESS_ACCOUNT_ID.", 500
        return render_template('index.html', media_list=media_list)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/debug')
def debug():
    debug_info = {
        'has_access_token': bool(ACCESS_TOKEN),
        'app_id': INSTAGRAM_APP_ID,
        'business_account': BUSINESS_ACCOUNT_ID,
        'username': INSTAGRAM_USERNAME
    }
    return jsonify(debug_info)

@app.route('/media/<media_id>/comments')
def media_comments(media_id):
    comments = get_comments(media_id)
    return jsonify(comments)

@app.route('/comment/<comment_id>/reply', methods=['POST'])
def post_reply(comment_id):
    message = request.json.get('message')
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    success, response = reply_to_comment(comment_id, message)
    if success:
        return jsonify({"success": True, "response": response})
    return jsonify({"error": "Failed to post reply", "response": response}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=51968)