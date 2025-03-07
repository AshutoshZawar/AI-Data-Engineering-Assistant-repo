# src/utils/db_utils.py

import os
import yaml
from pymongo import MongoClient
from datetime import datetime

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

class MongoDBHandler:
    def __init__(self):
        config = load_config()
        self.mongo_uri = os.getenv("MONGODB_URI", config.get("mongodb_uri"))
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client.pipeline_logs
        self.logs_collection = self.db.logs
    
    def insert_log(self, level, message, pipeline=None):
        """
        Insert a log entry into MongoDB
        
        Args:
            level (str): Log level (INFO, WARNING, ERROR, etc.)
            message (str): Log message
            pipeline (str, optional): Pipeline identifier
        """
        log_entry = {
            "timestamp": datetime.now(),
            "level": level,
            "message": message,
            "pipeline": pipeline
        }
        
        result = self.logs_collection.insert_one(log_entry)
        return result.inserted_id
    
    def fetch_logs(self, limit=10, pipeline=None, level=None):
        """
        Fetch logs from MongoDB with optional filtering
        
        Args:
            limit (int): Maximum number of logs to fetch
            pipeline (str, optional): Filter logs by pipeline
            level (str, optional): Filter logs by level
            
        Returns:
            list: List of log entries
        """
        query = {}
        
        if pipeline:
            query["pipeline"] = pipeline
            
        if level:
            query["level"] = level
            
        logs = self.logs_collection.find(query).sort("timestamp", -1).limit(limit)
        return list(logs)
    
    def insert_sample_logs(self):
        """
        Insert sample logs for testing
        """
        sample_logs = [
            {"timestamp": datetime.now(), "level": "ERROR", "message": "Airflow DAG failed due to missing dependencies", "pipeline": "ETL_Job_1"},
            {"timestamp": datetime.now(), "level": "INFO", "message": "Pipeline executed successfully in 120 seconds", "pipeline": "ETL_Job_2"},
            {"timestamp": datetime.now(), "level": "WARNING", "message": "Data quality check: 5% of records have missing values", "pipeline": "ETL_Job_1"},
            {"timestamp": datetime.now(), "level": "ERROR", "message": "Connection timeout while accessing data source", "pipeline": "ETL_Job_3"},
            {"timestamp": datetime.now(), "level": "INFO", "message": "Processed 1.2 million records successfully", "pipeline": "ETL_Job_2"},
        ]
        
        self.logs_collection.insert_many(sample_logs)
        print("Sample logs inserted.")

# Test the MongoDB handler
if __name__ == "__main__":
    db_handler = MongoDBHandler()
    db_handler.insert_sample_logs()
    
    # Fetch and print logs
    logs = db_handler.fetch_logs(limit=5)
    for log in logs:
        print(f"{log['timestamp']} - {log['level']} - {log['message']}")