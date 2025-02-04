import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from instagrapi import Client
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Instagram credentials
USERNAME = os.getenv('INSTAGRAM_USERNAME')
PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

# Initialize Instagram client
cl = Client()
cl.login(USERNAME, PASSWORD)

def format_timestamp(timestamp):
    if isinstance(timestamp, int):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return timestamp

@app.route('/')
def index():
    try:
        # Get user's media
        user_id = cl.user_id
        medias = cl.user_medias(user_id, 20)  # Get last 20 posts
        
        media_list = []
        for media in medias:
            media_list.append({
                'id': media.id,
                'caption': media.caption_text if media.caption_text else '',
                'comments_count': media.comment_count,
                'timestamp': format_timestamp(media.taken_at.timestamp()),
                'permalink': f'https://www.instagram.com/p/{media.code}/',
                'thumbnail': media.thumbnail_url
            })
        
        return render_template('index.html', media_list=media_list)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/media/<media_id>/comments')
def media_comments(media_id):
    try:
        comments = cl.media_comments(media_id)
        comment_list = []
        
        for comment in comments:
            comment_data = {
                'id': comment.pk,
                'text': comment.text,
                'username': comment.user.username,
                'timestamp': format_timestamp(comment.created_at_utc.timestamp()),
                'replies': []
            }
            
            # Get comment replies if any exist
            try:
                replies = cl.media_comments_chunk(media_id, max_id=comment.pk)
                for reply in replies:
                    if hasattr(reply, 'parent_comment_id') and reply.parent_comment_id == comment.pk:
                        comment_data['replies'].append({
                            'id': reply.pk,
                            'text': reply.text,
                            'username': reply.user.username,
                            'timestamp': format_timestamp(reply.created_at_utc.timestamp())
                        })
            except Exception as e:
                print(f"Error getting replies for comment {comment.pk}: {e}")
            
            comment_list.append(comment_data)
        
        return jsonify(comment_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/comment/<comment_id>/reply', methods=['POST'])
def post_reply(comment_id):
    try:
        message = request.json.get('message')
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        # Get the media ID from the comment
        comment = cl.comment_info(comment_id)
        media_id = comment.media_id
        
        # Post the reply
        reply = cl.media_comment(media_id, message, replied_to_comment_id=comment_id)
        
        return jsonify({
            "success": True,
            "reply": {
                "id": reply.pk,
                "text": reply.text,
                "username": reply.user.username,
                "timestamp": format_timestamp(reply.created_at_utc.timestamp())
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=51968)