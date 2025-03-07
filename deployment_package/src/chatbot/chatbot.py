# src/chatbot/chatbot.py

import os
import yaml
import openai
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

# Initialize components
config = load_config()
console = Console()
openai.api_key = os.getenv("OPENAI_API_KEY", config.get("openai_api_key"))

def chat_with_ai(prompt):
    """
    Interact with OpenAI's GPT model to get answers related to data engineering.
    
    Args:
        prompt (str): User's input/question
        
    Returns:
        str: AI-generated response
    """
    try:
        # Check OpenAI client version and use appropriate API
        import pkg_resources
        openai_version = pkg_resources.get_distribution("openai").version
        
        if int(openai_version.split('.')[0]) >= 1:
            # New OpenAI client (>=1.0.0)
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", config.get("openai_api_key")))
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a data pipeline debugging assistant specialized in helping data engineers optimize, debug, and monitor their data pipelines. You have expertise in tools like Airflow, Spark, Kafka, and various ETL processes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            return response.choices[0].message.content
        else:
            # Legacy OpenAI client (<1.0.0)
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a data pipeline debugging assistant specialized in helping data engineers optimize, debug, and monitor their data pipelines. You have expertise in tools like Airflow, Spark, Kafka, and various ETL processes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            return response["choices"][0]["message"]["content"]
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return "I'm having trouble connecting to the AI service. Please check your API key and internet connection."

def run_cli():
    """
    Run the CLI-based chat interface
    """
    console.print(Panel.fit("AI-Powered Automated Data Engineering Assistant (ADEA)", title="Welcome", subtitle="Type 'exit' to quit"))
    
    while True:
        user_input = console.input("[bold blue]You:[/bold blue] ")
        
        if user_input.lower() in ["exit", "quit", "bye"]:
            console.print("[bold green]Thank you for using ADEA. Goodbye![/bold green]")
            break
            
        if user_input.strip() == "":
            continue
            
        # Log the query for future reference
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("query_logs.txt", "a") as log_file:
            log_file.write(f"{timestamp} - Query: {user_input}\n")
            
        # Process special commands
        if user_input.lower() == "help":
            show_help()
            continue
            
        # Get AI response
        console.print("[bold yellow]AI Assistant is thinking...[/bold yellow]")
        response = chat_with_ai(user_input)
        
        # Display the response
        console.print(f"[bold green]AI:[/bold green] {response}")

def show_help():
    """
    Display help information
    """
    help_text = """
    Available Commands:
    - 'exit', 'quit', 'bye': Exit the application
    - 'help': Show this help message
    
    Example Questions:
    - "How do I debug a failed Airflow DAG?"
    - "What are common causes of data inconsistencies in ETL pipelines?"
    - "How can I optimize my Spark job that's running slowly?"
    - "What metrics should I monitor for my data warehouse?"
    """
    console.print(Panel(help_text, title="Help"))

if __name__ == "__main__":
    run_cli()