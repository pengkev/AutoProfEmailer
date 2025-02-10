import os
import sqlite3
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

def setup_email_database():
    """Create database directory and database if they don't exist"""
    # Update database path to use src/databases
    db_dir = os.path.join(os.path.dirname(__file__), '..', 'databases')
    os.makedirs(db_dir, exist_ok=True)
    
    # Connect to database
    db_path = os.path.join(db_dir, 'templated_emails.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create simplified table for storing emails
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templated_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_name TEXT NOT NULL,
            department TEXT NOT NULL,
            email_content TEXT NOT NULL,
            UNIQUE(professor_name, department)
        )
    """)
    conn.commit()
    return conn

def generate_and_save_email(professor_name, department, paper_title):
    """Generate email and save to database"""
    # Generate email content
    email_content = generate_email(professor_name, paper_title)
    
    # Save to database
    conn = setup_email_database()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO templated_emails 
            (professor_name, department, email_content)
            VALUES (?, ?, ?)
        """, (professor_name, department, email_content))
        conn.commit()
        print(f"Email saved for Professor {professor_name}")
    except Exception as e:
        print(f"Error saving email: {e}")
    finally:
        conn.close()
    
    return email_content

def generate_email(professor_name, paper_title):
    """
    Generate an email using a template and professor-specific information
    """
    # Setup Jinja2 template environment
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('email_template.j2')
    
    # Extract first name if possible
    last_name = professor_name.split()[-1]
    
    # Render template with professor info
    email_content = template.render(
        name=last_name,
        paper_title=paper_title,
        student_name="Kevin Peng",
        student_program="Engineering Science"
    )
    
    return email_content