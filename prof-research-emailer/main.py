import os
import sqlite3
from src.scrapers.faculty_scraper import scrape_professors
from src.scrapers.scholar_scraper import search_recent_publications
from src.utils.email_generator import generate_and_save_email

def main():
    # Update database path to use src/databases
    db_dir = os.path.join(os.path.dirname(__file__), 'src', 'databases')
    os.makedirs(db_dir, exist_ok=True)
    
    db_path = os.path.join(db_dir, 'uoft_professors.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS professors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            UNIQUE(name, department)
        )
    """)
    
    # Scrape professors
    print("Scraping faculty data...")
    scrape_professors()
    
    # Get all professors from database
    cursor.execute("SELECT name, department FROM professors")
    professors = cursor.fetchall()
    
    # Generate emails for each professor
    for prof_name, department in professors:
        print(f"\nProcessing {prof_name} from {department} department...")
        
        # Get recent publications
        publications = search_recent_publications(prof_name)
        
        if publications:
            recent_pub = publications[0]  # Get the most recent publication
            print(f"Found publication: {recent_pub['title']}")
            
            # Generate email
            email = generate_and_save_email(prof_name, department, recent_pub['title'])
            print("\nGenerated email:")
            print("=" * 50)
            print(email)
            print("=" * 50)
        else:
            print(f"No publications found for {prof_name}")
    
    conn.close()

if __name__ == "__main__":
    main()