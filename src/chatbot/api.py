import os
import json
import time
import redis
import hashlib
import logging
from flask import Flask, request, jsonify, Response
from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest
import sys
from datetime import datetime

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.chatbot.chatbot import chat_with_ai, load_config
from src.anomaly_detection.detector import AnomalyDetector
from src.utils.db_utils import MongoDBHandler

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config = load_config()

# Configure Redis for caching
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_cache = redis.Redis(host=redis_host, port=redis_port, db=0)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize MongoDB handler and Anomaly Detector
db_handler = MongoDBHandler()
anomaly_detector = AnomalyDetector()
try:
    anomaly_detector.train_model()  # Pre-train the model
except Exception as e:
    logger.error(f"Error training anomaly detection model: {str(e)}")

# Define Prometheus metrics
REQUEST_COUNT = Counter('adea_requests_total', 'Total request count', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('adea_request_latency_seconds', 'Request latency', ['endpoint'])
RESPONSE_SIZE = Histogram('adea_response_size_bytes', 'Response size in bytes', ['endpoint'])
API_ERRORS = Counter('adea_api_errors_total', 'API error count', ['endpoint', 'error_type'])
ACTIVE_REQUESTS = Gauge('adea_active_requests', 'Number of active requests')
CACHE_HITS = Counter('adea_cache_hits_total', 'Number of cache hits')
CACHE_MISSES = Counter('adea_cache_misses_total', 'Number of cache misses')
ANOMALIES_DETECTED = Counter('adea_anomalies_detected_total', 'Number of anomalies detected')
MODEL_TRAIN_TIME = Summary('adea_model_train_time_seconds', 'Time spent training the model')
LOG_COUNT = Gauge('adea_log_count', 'Number of logs in database', ['level'])

# Create a caching function for API responses
def get_cached_response(cache_key, expiration=3600):
    """
    Get cached response from Redis
    
    Args:
        cache_key (str): The key to look up in cache
        expiration (int): Cache expiration time in seconds
        
    Returns:
        str or None: Cached response or None if not found
    """
    try:
        cached = redis_cache.get(cache_key)
        if cached:
            CACHE_HITS.inc()
            return cached.decode('utf-8')
        CACHE_MISSES.inc()
        return None
    except Exception as e:
        logger.error(f"Cache error: {str(e)}")
        CACHE_MISSES.inc()
        return None

def set_cached_response(cache_key, response, expiration=3600):
    """
    Cache response in Redis
    
    Args:
        cache_key (str): Cache key
        response (str): Response to cache
        expiration (int): Cache expiration time in seconds
    """
    try:
        redis_cache.set(cache_key, response, ex=expiration)
    except Exception as e:
        logger.error(f"Error setting cache: {str(e)}")

def generate_cache_key(message):
    """
    Generate a cache key from the message
    
    Args:
        message (str): User message
        
    Returns:
        str: Cache key
    """
    return hashlib.md5(message.encode()).hexdigest()

@app.before_request
def before_request():
    """Middleware to run before each request"""
    request.start_time = time.time()
    ACTIVE_REQUESTS.inc()
    
@app.after_request
def after_request(response):
    """Middleware to run after each request"""
    request_latency = time.time() - request.start_time
    REQUEST_LATENCY.labels(endpoint=request.endpoint).observe(request_latency)
    
    # Count status codes
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.endpoint or 'unknown',
        status=response.status_code
    ).inc()
    
    # Track response size
    response_size = len(response.get_data())
    RESPONSE_SIZE.labels(endpoint=request.endpoint or 'unknown').observe(response_size)
    
    ACTIVE_REQUESTS.dec()
    return response

@app.route("/metrics")
def metrics():
    """Endpoint for Prometheus metrics"""
    # Update log count metrics
    for level in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
        count = db_handler.logs_collection.count_documents({"level": level})
        LOG_COUNT.labels(level=level).set(count)
    
    return Response(generate_latest(), mimetype="text/plain")

@app.route("/", methods=["GET"])
def index():
    """Root endpoint with API information"""
    return jsonify({
        "name": "AI-Powered Automated Data Engineering Assistant API",
        "version": "1.1.0",
        "endpoints": [
            {"path": "/", "methods": ["GET"], "description": "API information"},
            {"path": "/chat", "methods": ["POST"], "description": "Chat with the AI assistant"},
            {"path": "/anomalies", "methods": ["GET"], "description": "Detect anomalies in logs"},
            {"path": "/logs", "methods": ["GET"], "description": "Get recent logs"},
            {"path": "/metrics", "methods": ["GET"], "description": "Get Prometheus metrics"}
        ]
    })

@app.route("/chat", methods=["POST"])
def chat():
    """Endpoint for chatting with the AI assistant"""
    try:
        # Get user input from JSON or form data
        if request.is_json:
            user_input = request.json.get("message", "")
        else:
            user_input = request.form.get("message", "")
        
        if not user_input:
            API_ERRORS.labels(endpoint="/chat", error_type="missing_message").inc()
            return jsonify({"error": "Message is required"}), 400
            
        # Check if the response is cached
        cache_key = generate_cache_key(user_input)
        cached_response = get_cached_response(cache_key)
        
        if cached_response:
            # Log the cached response
            db_handler.insert_log(
                level="INFO",
                message=f"Cached response for: {user_input[:50]}...",
                pipeline="CHATBOT_CACHED"
            )
            
            return jsonify({"response": cached_response, "cached": True})
        
        # Get AI response
        response = chat_with_ai(user_input)
        
        # Cache the response
        set_cached_response(cache_key, response)
        
        # Log the conversation
        db_handler.insert_log(
            level="INFO",
            message=f"User query: {user_input[:50]}... | Response length: {len(response)}",
            pipeline="CHATBOT"
        )
        
        return jsonify({"response": response, "cached": False})
    except Exception as e:
        logger.exception("Error processing chat request")
        API_ERRORS.labels(endpoint="/chat", error_type="server_error").inc()
        return jsonify({"error": str(e)}), 500

@app.route("/anomalies", methods=["GET"])
def anomalies():
    """Endpoint for detecting anomalies in logs"""
    try:
        # Fetch recent logs
        pipeline = request.args.get("pipeline")
        level = request.args.get("level")
        limit = int(request.args.get("limit", 100))
        
        logs = db_handler.fetch_logs(limit=limit, pipeline=pipeline, level=level)
        
        # Detect anomalies
        start_time = time.time()
        detected_anomalies = anomaly_detector.detect_anomalies(logs)
        detection_time = time.time() - start_time
        
        # Update Prometheus metrics
        ANOMALIES_DETECTED.inc(len(detected_anomalies))
        
        # Format response
        result = []
        for anomaly in detected_anomalies:
            result.append({
                "timestamp": anomaly["timestamp"].isoformat(),
                "level": anomaly["level"],
                "message": anomaly["message"],
                "pipeline": anomaly["pipeline"]
            })
        
        db_handler.insert_log(
            level="INFO",
            message=f"Anomaly detection completed in {detection_time:.2f}s. Found {len(detected_anomalies)} anomalies.",
            pipeline="ANOMALY_DETECTOR"
        )
        
        return jsonify({
            "total_logs": len(logs),
            "anomalies_detected": len(detected_anomalies),
            "execution_time_seconds": detection_time,
            "anomalies": result
        })
    except Exception as e:
        logger.exception("Error detecting anomalies")
        API_ERRORS.labels(endpoint="/anomalies", error_type="server_error").inc()
        return jsonify({"error": str(e)}), 500

@app.route("/logs", methods=["GET"])
def get_logs():
    """Endpoint for fetching logs"""
    try:
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
    except Exception as e:
        logger.exception("Error fetching logs")
        API_ERRORS.labels(endpoint="/logs", error_type="server_error").inc()
        return jsonify({"error": str(e)}), 500

@app.route("/retrain", methods=["POST"])
def retrain_model():
    """Endpoint to retrain the anomaly detection model"""
    try:
        with MODEL_TRAIN_TIME.time():
            success = anomaly_detector.train_model()
        
        if success:
            return jsonify({"status": "success", "message": "Model retrained successfully"})
        else:
            API_ERRORS.labels(endpoint="/retrain", error_type="training_failure").inc()
            return jsonify({"status": "error", "message": "Failed to retrain model"}), 500
    except Exception as e:
        logger.exception("Error retraining model")
        API_ERRORS.labels(endpoint="/retrain", error_type="server_error").inc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    logger.info(f"Starting ADEA API on {host}:{port}")
    app.run(host=host, port=port, debug=debug)