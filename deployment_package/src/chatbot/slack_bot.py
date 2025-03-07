# src/chatbot/slack_bot_windows.py

import os
import sys
import yaml
import argparse
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, jsonify

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.chatbot.chatbot import chat_with_ai, load_config
from src.utils.db_utils import MongoDBHandler

# Parse command line arguments
parser = argparse.ArgumentParser(description="Slack Bot for Data Engineering Assistant")
parser.add_argument("--port", type=int, default=5001, help="Port to run the Flask server on")
parser.add_argument("--host", type=str, default="localhost", help="Host to bind the Flask server to")
parser.add_argument("--debug", action="store_true", help="Run Flask in debug mode")
args = parser.parse_args()

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config = load_config()
slack_token = os.getenv("SLACK_BOT_TOKEN", config.get("slack_token"))
client = WebClient(token=slack_token)

# Initialize MongoDB handler
db_handler = MongoDBHandler()

@app.route("/", methods=["GET"])
def index():
    """Root endpoint with information"""
    return jsonify({
        "name": "ADEA Slack Bot",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            {
                "path": "/slack/events",
                "method": "POST",
                "description": "Endpoint for Slack events"
            }
        ]
    })

@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events"""
    data = request.json
    
    # Slack URL verification
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    # Handle events
    if "event" in data:
        event = data["event"]
        
        # Handle message events
        if event["type"] == "message" and "subtype" not in event:
            user_message = event["text"]
            channel_id = event["channel"]
            user_id = event["user"]
            
            # Check if message is directed to the bot (@ mentions)
            if f"<@{client.auth_test()['user_id']}>" in user_message:
                # Remove the bot mention from the message
                user_message = user_message.replace(f"<@{client.auth_test()['user_id']}>", "").strip()
                
                # Log the message
                db_handler.insert_log(
                    level="INFO",
                    message=f"Slack message from {user_id}: {user_message}",
                    pipeline="SLACK_BOT"
                )
                
                # Process the message
                process_message(user_message, channel_id, user_id)
    
    return jsonify({"status": "ok"})

def process_message(message, channel_id, user_id):
    """Process a message from Slack and send a response"""
    try:
        # Get AI response
        response = chat_with_ai(message)
        
        # Send the response
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> {response}"
        )
        
        # Log the response
        db_handler.insert_log(
            level="INFO",
            message=f"Response sent to {user_id} in channel {channel_id}",
            pipeline="SLACK_BOT"
        )
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
        db_handler.insert_log(
            level="ERROR",
            message=f"Slack API error: {e.response['error']}",
            pipeline="SLACK_BOT"
        )

def send_message(channel, message):
    """Send a message to a Slack channel"""
    try:
        client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

if __name__ == "__main__":
    # Test the Slack connection
    try:
        client.auth_test()
        print("Slack connection successful!")
    except SlackApiError as e:
        print(f"Slack connection failed: {e.response['error']}")
    
    # Show startup message
    print(f"Starting Slack bot server on {args.host}:{args.port}")
    print("Press Ctrl+C to stop the server")
    
    # Run the Flask app - use localhost instead of 0.0.0.0 for Windows compatibility
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug
        )
    except Exception as e:
        print(f"Error starting Flask app: {str(e)}")
        print("\nTroubleshooting tips for Windows:")
        print("1. Try running as Administrator")
        print("2. Make sure no other application is using the port")
        print("3. Try using a port number above 1024 (e.g., --port=8080)")
        print("4. Check your firewall settings")