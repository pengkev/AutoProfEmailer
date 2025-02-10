# Quick database check script
import sqlite3
from pathlib import Path

def check_databases():
    db_dir = Path(__file__).parent.parent / 'databases'
    
    # Check professors.db
    prof_db = db_dir / 'uoft_professors.db'
    if prof_db.exists():
        conn = sqlite3.connect(prof_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM professors")
        count = cursor.fetchone()[0]
        print(f"Found {count} professors in database")
        conn.close()
    else:
        print("professors.db not found - run faculty_scraper.py first")

    # Check validated_emails.db
    valid_db = db_dir / 'validated_emails.db'
    if valid_db.exists():
        conn = sqlite3.connect(valid_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM validated_emails")
        count = cursor.fetchone()[0]
        print(f"Found {count} validated emails")
        conn.close()
    else:
        print("validated_emails.db not found - run email_validator.py first")

if __name__ == "__main__":
    check_databases()