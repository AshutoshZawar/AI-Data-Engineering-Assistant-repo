# src/main.py

import os
import sys
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.chatbot.chatbot import run_cli, chat_with_ai
from src.utils.db_utils import MongoDBHandler
from src.anomaly_detection.detector import AnomalyDetector

# Initialize components
console = Console()
db_handler = MongoDBHandler()
anomaly_detector = AnomalyDetector()

def show_menu():
    """Display the main menu"""
    console.print(Panel.fit(
        "[bold]AI-Powered Automated Data Engineering Assistant (ADEA)[/bold]\n\n"
        "1. Start Chat Assistant\n"
        "2. View Recent Logs\n"
        "3. Detect Anomalies\n"
        "4. Insert Sample Logs\n"
        "5. Start Web API\n"
        "0. Exit",
        title="Main Menu"
    ))
    
    choice = console.input("[bold blue]Enter your choice (0-5):[/bold blue] ")
    return choice

def display_logs(logs):
    """Display logs in a table format"""
    table = Table(title="Pipeline Logs")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Level", style="magenta")
    table.add_column("Pipeline", style="green")
    table.add_column("Message", style="white")
    
    for log in logs:
        table.add_row(
            log["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            log["level"],
            log.get("pipeline", "N/A"),
            log["message"]
        )
    
    console.print(table)

def display_anomalies(anomalies):
    """Display anomalies in a table format"""
    table = Table(title="Detected Anomalies")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Level", style="magenta")
    table.add_column("Pipeline", style="green")
    table.add_column("Message", style="white")
    
    for anomaly in anomalies:
        table.add_row(
            anomaly["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            anomaly["level"],
            anomaly.get("pipeline", "N/A"),
            anomaly["message"]
        )
    
    console.print(table)

def view_logs():
    """View recent logs from the database"""
    console.print("[bold]Fetching recent logs...[/bold]")
    
    # Get optional filters
    pipeline = console.input("[bold blue]Filter by pipeline (leave empty for all):[/bold blue] ")
    level = console.input("[bold blue]Filter by level (INFO/WARNING/ERROR/CRITICAL, leave empty for all):[/bold blue] ")
    
    # Validate level input
    if level and level not in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
        console.print("[bold red]Invalid level! Using no filter.[/bold red]")
        level = None
    
    # Fetch logs
    logs = db_handler.fetch_logs(limit=20, pipeline=pipeline if pipeline else None, level=level if level else None)
    
    if not logs:
        console.print("[bold yellow]No logs found with the current filters.[/bold yellow]")
    else:
        display_logs(logs)

def detect_anomalies():
    """Detect anomalies in the logs"""
    console.print("[bold]Training anomaly detection model...[/bold]")
    anomaly_detector.train_model()
    
    console.print("[bold]Detecting anomalies...[/bold]")
    anomalies = anomaly_detector.detect_anomalies()
    
    if not anomalies:
        console.print("[bold green]No anomalies detected![/bold green]")
    else:
        console.print(f"[bold red]Detected {len(anomalies)} anomalies:[/bold red]")
        display_anomalies(anomalies)

def insert_sample_logs():
    """Insert sample logs into the database"""
    db_handler.insert_sample_logs()
    console.print("[bold green]Sample logs inserted successfully![/bold green]")

def start_web_api():
    """Start the Flask web API"""
    console.print("[bold]Starting Web API...[/bold]")
    console.print("[bold yellow]Press Ctrl+C to stop the API[/bold yellow]")
    
    try:
        # Import the API module
        from src.chatbot.api import app
        
        # Run the Flask app
        app.run(host="0.0.0.0", port=5000, debug=True)
    except KeyboardInterrupt:
        console.print("[bold]API stopped.[/bold]")
    except Exception as e:
        console.print(f"[bold red]Error starting API: {str(e)}[/bold red]")

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description="AI-Powered Automated Data Engineering Assistant")
    parser.add_argument("--cli", action="store_true", help="Start CLI chat directly")
    parser.add_argument("--api", action="store_true", help="Start Web API directly")
    args = parser.parse_args()
    
    # Direct start based on arguments
    if args.cli:
        run_cli()
        return
    
    if args.api:
        start_web_api()
        return
    
    # Interactive menu
    while True:
        choice = show_menu()
        
        if choice == "0":
            console.print("[bold green]Thank you for using ADEA. Goodbye![/bold green]")
            break
        elif choice == "1":
            run_cli()
        elif choice == "2":
            view_logs()
        elif choice == "3":
            detect_anomalies()
        elif choice == "4":
            insert_sample_logs()
        elif choice == "5":
            start_web_api()
        else:
            console.print("[bold red]Invalid choice! Please try again.[/bold red]")

if __name__ == "__main__":
    main()