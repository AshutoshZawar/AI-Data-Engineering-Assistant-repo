# src/anomaly_detection/detector.py

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import sys
import os

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils.db_utils import MongoDBHandler

class AnomalyDetector:
    def __init__(self):
        self.model = None
        self.db_handler = MongoDBHandler()
        self.level_mapping = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
        self.scaler = StandardScaler()
        
    def train_model(self):
        """
        Train an Isolation Forest model to detect anomalies in logs
        """
        # Fetch logs from MongoDB
        logs = self.db_handler.fetch_logs(limit=1000)
        
        if not logs:
            print("No logs found for training. Please insert some logs first.")
            return False
            
        # Extract features for anomaly detection
        features = []
        for log in logs:
            # Use log level as a feature
            level_value = self.level_mapping.get(log.get("level", "INFO"), 0)
            
            # Use pipeline as a categorical feature (simple encoding)
            pipeline_hash = hash(log.get("pipeline", "unknown")) % 10
            
            # Extract time-based features
            timestamp = log.get("timestamp")
            hour_of_day = timestamp.hour if timestamp else 0
            
            # Create feature vector
            feature_vector = [level_value, pipeline_hash, hour_of_day]
            features.append(feature_vector)
            
        # Convert to numpy array
        X = np.array(features)
        
        # Scale the features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train the Isolation Forest model
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.model.fit(X_scaled)
        
        print("Anomaly detection model trained successfully.")
        return True
        
    def detect_anomalies(self, logs=None):
        """
        Detect anomalies in logs using the trained model
        
        Args:
            logs (list, optional): List of log entries. If None, fetch logs from MongoDB
            
        Returns:
            list: List of anomalous logs
        """
        if not self.model:
            print("Model not trained. Training now...")
            if not self.train_model():
                return []
                
        # Fetch logs if not provided
        if not logs:
            logs = self.db_handler.fetch_logs(limit=100)
            
        if not logs:
            return []
            
        # Extract features for anomaly detection
        features = []
        for log in logs:
            # Use log level as a feature
            level_value = self.level_mapping.get(log.get("level", "INFO"), 0)
            
            # Use pipeline as a categorical feature (simple encoding)
            pipeline_hash = hash(log.get("pipeline", "unknown")) % 10
            
            # Extract time-based features
            timestamp = log.get("timestamp")
            hour_of_day = timestamp.hour if timestamp else 0
            
            # Create feature vector
            feature_vector = [level_value, pipeline_hash, hour_of_day]
            features.append(feature_vector)
            
        # Convert to numpy array
        X = np.array(features)
        
        # Scale the features
        X_scaled = self.scaler.transform(X)
        
        # Predict anomalies
        predictions = self.model.predict(X_scaled)
        
        # Filter anomalous logs (predictions == -1)
        anomalous_logs = [log for log, pred in zip(logs, predictions) if pred == -1]
        
        return anomalous_logs

# Test the anomaly detector
if __name__ == "__main__":
    detector = AnomalyDetector()
    
    # Create sample logs for testing if needed
    db_handler = MongoDBHandler()
    db_handler.insert_sample_logs()
    
    # Train the model
    detector.train_model()
    
    # Detect anomalies
    anomalies = detector.detect_anomalies()
    
    print(f"Detected {len(anomalies)} anomalies:")
    for anomaly in anomalies:
        print(f"{anomaly['timestamp']} - {anomaly['level']} - {anomaly['pipeline']} - {anomaly['message']}")