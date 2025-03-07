# src/utils/compliance.py

import logging
from cryptography.fernet import Fernet
import os

# Set up logging
logging.basicConfig(filename="audit.log", level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate or load encryption key
def get_encryption_key():
    key_file = "encryption.key"
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
        return key

# Initialize encryption
key = get_encryption_key()
cipher = Fernet(key)

def encrypt_data(data):
    """Encrypt sensitive data"""
    if isinstance(data, str):
        return cipher.encrypt(data.encode()).decode()
    return data

def decrypt_data(data):
    """Decrypt sensitive data"""
    if isinstance(data, str):
        try:
            return cipher.decrypt(data.encode()).decode()
        except:
            return data
    return data

def anonymize_log(log):
    """Remove PII from logs"""
    # Clone the log to avoid modifying the original
    anonymized = log.copy()
    
    # Anonymize user identifiers
    if "user_id" in anonymized:
        anonymized["user_id"] = "ANONYMIZED"
    
    # Anonymize IP addresses
    if "remote_addr" in anonymized:
        anonymized["remote_addr"] = "XXX.XXX.XXX.XXX"
    
    # Anonymize message content if needed
    if "message" in anonymized and isinstance(anonymized["message"], str):
        # Check if message might contain emails or other PII
        if "@" in anonymized["message"] or any(term in anonymized["message"].lower() for term in ["password", "social", "credit", "ssn"]):
            # Redact potentially sensitive parts
            words = anonymized["message"].split()
            for i, word in enumerate(words):
                if "@" in word or any(term in word.lower() for term in ["password", "social", "credit", "ssn"]):
                    words[i] = "[REDACTED]"
            anonymized["message"] = " ".join(words)
    
    return anonymized

def log_api_request(request, user_id=None):
    """Log API requests for auditing"""
    log_data = {
        "timestamp": str(datetime.now()),
        "method": request.method,
        "path": request.path,
        "remote_addr": request.remote_addr,
        "user_id": user_id or "anonymous"
    }
    
    # Anonymize before logging
    anonymized_log = anonymize_log(log_data)
    logger.info(f"API Request: {anonymized_log}")
    
    return anonymized_log