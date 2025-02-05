import json
import requests
import os

def reply_to_instagram_comment(params_json: str) -> str:
    """
    Reply to an Instagram comment using the instaserver API.
    
    Args:
        params_json: A JSON string containing:
            - media_id: The ID of the Instagram post
            - comment_id: The ID of the comment to reply to
            - reply_text: The text of the reply
    
    Returns:
        str: A message indicating success or failure of the reply
    
    Example:
        >>> reply_to_instagram_comment('{"media_id": "123456789", "comment_id": "987654321", "reply_text": "Thank you!"}')
        "Successfully replied to comment: Thank you!"
    """
    try:
        # Parse parameters
        params = json.loads(params_json)
        
        # Validate required parameters
        required_fields = ['media_id', 'comment_id', 'reply_text']
        missing_fields = [field for field in required_fields if field not in params]
        if missing_fields:
            return f"Error: Missing required fields: {', '.join(missing_fields)}"
        
        # Configuration
        BASE_URL = os.environ.get("INSTASERVER_URL", "http://localhost:52810")
        
        # Prepare request
        url = f"{BASE_URL}/test/reply"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "media_id": params['media_id'],
            "comment_id": params['comment_id'],
            "reply_text": params['reply_text']
        }
        
        # Send request
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                reply = result.get('reply', {})
                return (
                    f"Successfully replied to comment!\n"
                    f"Reply text: {reply.get('text')}\n"
                    f"Posted by: @{reply.get('username')}\n"
                    f"At: {reply.get('timestamp')}"
                )
            return f"Error: {result.get('error', 'Unknown error')}"
        
        return f"Error: API request failed with status code {response.status_code}"
    
    except json.JSONDecodeError:
        return "Error: Invalid JSON parameters"
    except requests.RequestException as e:
        return f"Error: Network error - {str(e)}"
    except Exception as e:
        return f"Error: Unexpected error - {str(e)}"

def post_instagram_comment(params_json: str) -> str:
    """
    Post a new comment on an Instagram post using the instaserver API.
    
    Args:
        params_json: A JSON string containing:
            - media_id: The ID of the Instagram post
            - text: The text of the comment
    
    Returns:
        str: A message indicating success or failure of the comment
    
    Example:
        >>> post_instagram_comment('{"media_id": "123456789", "text": "Great post!"}')
        "Successfully posted comment: Great post!"
    """
    try:
        # Parse parameters
        params = json.loads(params_json)
        
        # Validate required parameters
        required_fields = ['media_id', 'text']
        missing_fields = [field for field in required_fields if field not in params]
        if missing_fields:
            return f"Error: Missing required fields: {', '.join(missing_fields)}"
        
        # Configuration
        BASE_URL = os.environ.get("INSTASERVER_URL", "http://localhost:52810")
        
        # Prepare request
        url = f"{BASE_URL}/test/comment"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "media_id": params['media_id'],
            "text": params['text']
        }
        
        # Send request
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                comment = result.get('comment', {})
                return (
                    f"Successfully posted comment!\n"
                    f"Comment text: {comment.get('text')}\n"
                    f"Posted by: @{comment.get('username')}\n"
                    f"At: {comment.get('timestamp')}"
                )
            return f"Error: {result.get('error', 'Unknown error')}"
        
        return f"Error: API request failed with status code {response.status_code}"
    
    except json.JSONDecodeError:
        return "Error: Invalid JSON parameters"
    except requests.RequestException as e:
        return f"Error: Network error - {str(e)}"
    except Exception as e:
        return f"Error: Unexpected error - {str(e)}"