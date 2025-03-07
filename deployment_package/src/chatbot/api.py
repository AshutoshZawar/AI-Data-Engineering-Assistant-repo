# src/chatbot/api.py

from flask import Flask, request, jsonify, Response
import sys
import os
from prometheus_client import Counter, generate_latest
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import logging

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.chatbot.chatbot import chat_with_ai, load_config
from src.anomaly_detection.detector import AnomalyDetector
from src.utils.db_utils import MongoDBHandler

# Initialize Flask app
app = Flask(__name__)

# Configure JWT
config = load_config()
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "default-secret-key")  # Change this in production
jwt = JWTManager(app)

# Initialize MongoDB handler and Anomaly Detector
db_handler = MongoDBHandler()
anomaly_detector = AnomalyDetector()
anomaly_detector.train_model()  # Pre-train the model

# Configure logging
logging.basicConfig(
    filename='api.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Prometheus metrics
request_counter = Counter('chatbot_requests_total', 'Total chatbot API requests')
anomaly_counter = Counter('detected_anomalies_total', 'Total anomalies detected')

@app.route("/metrics")
def metrics():
    """Endpoint for Prometheus metrics"""
    return Response(generate_latest(), mimetype="text/plain")

@app.route("/login", methods=["POST"])
def login():
    """Endpoint for JWT authentication"""
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    
    # Basic authentication (replace with proper auth in production)
    if username != "admin" or password != "password":
        return jsonify({"msg": "Invalid credentials"}), 401
        
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)

@app.route("/", methods=["GET"])
def index():
    """Root endpoint with API information"""
    return jsonify({
        "name": "AI-Powered Automated Data Engineering Assistant API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/login", "methods": ["POST"], "description": "Get JWT token"},
            {"path": "/chat", "methods": ["POST"], "description": "Chat with the AI assistant"},
            {"path": "/anomalies", "methods": ["GET"], "description": "Detect anomalies in logs"},
            {"path": "/logs", "methods": ["GET"], "description": "Get recent logs"},
            {"path": "/metrics", "methods": ["GET"], "description": "Get Prometheus metrics"}
        ]
    })

@app.route("/chat", methods=["POST"])
def chat():
    """Endpoint for chatting with the AI assistant"""
    request_counter.inc()
    
    # Check authentication (if not login endpoint)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # Allow unauthenticated requests for testing
        logging.warning("Unauthenticated chat request")
    else:
        try:
            # Verify JWT token
            from flask_jwt_extended import decode_token
            token = auth_header.split(' ')[1]
            decoded_token = decode_token(token)
            current_user = decoded_token["sub"]
            logging.info(f"Chat request from {current_user}")
        except Exception as e:
            logging.warning(f"Invalid token: {str(e)}")
    
    # Get user input
    if request.is_json:
        user_input = request.json.get("message", "")
    else:
        user_input = request.form.get("message", "")
    
    if not user_input:
        return jsonify({"error": "Message is required"}), 400
        
    # Get AI response
    response = chat_with_ai(user_input)
    
    # Log the conversation
    db_handler.insert_log(
        level="INFO",
        message=f"User query: {user_input} | Response length: {len(response)}",
        pipeline="CHATBOT"
    )
    
    return jsonify({"response": response})

@app.route("/anomalies", methods=["GET"])
@jwt_required()
def anomalies():
    """Endpoint for detecting anomalies in logs"""
    # Fetch recent logs
    pipeline = request.args.get("pipeline")
    level = request.args.get("level")
    limit = int(request.args.get("limit", 100))
    
    logs = db_handler.fetch_logs(limit=limit, pipeline=pipeline, level=level)
    
    # Detect anomalies
    detected_anomalies = anomaly_detector.detect_anomalies(logs)
    
    # Update Prometheus counter
    anomaly_counter.inc(len(detected_anomalies))
    
    # Format response
    result = []
    for anomaly in detected_anomalies:
        result.append({
            "timestamp": anomaly["timestamp"].isoformat(),
            "level": anomaly["level"],
            "message": anomaly["message"],
            "pipeline": anomaly["pipeline"]
        })
    
    return jsonify({
        "total_logs": len(logs),
        "anomalies_detected": len(detected_anomalies),
        "anomalies": result
    })

@app.route("/logs", methods=["GET"])
@jwt_required()
def get_logs():
    """Endpoint for fetching logs"""
    pipeline = request.args.get("pipeline")
    level = request.args.get("level")
    limit = int(request.args.get("limit", 10))
    
    logs = db_handler.fetch_logs(limit=limit, pipeline=pipeline, level=level)
    
    # Format response
    result = []
    for log in logs:
        result.append({
            "timestamp": log["timestamp"].isoformat(),
            "level": log["level"],
            "message": log["message"],
            "pipeline": log["pipeline"]
        })
    
    return jsonify({"logs": result})

@app.before_request
def before_request():
    """Middleware to run before each request"""
    request_counter.inc()
    logging.info(f"Request: {request.method} {request.path} - {request.remote_addr}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)