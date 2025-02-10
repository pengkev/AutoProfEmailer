import os
import sqlite3
from pathlib import Path
import win32com.client
import time
from typing import List, Dict

class EmailSender:
    def __init__(self):
        self.setup_database()
        self.setup_outlook()
        self.check_databases()
        
    def setup_database(self):
        """Initialize database connection"""
        db_dir = Path(__file__).parent.parent / 'databases'
        self.validated_db = db_dir / 'validated_emails.db'
        self.sent_db = db_dir / 'sent_emails.db'
        
        # Setup sent emails tracking
        conn = sqlite3.connect(self.sent_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT NOT NULL,
                professor_email TEXT NOT NULL,
                email_content TEXT NOT NULL,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                UNIQUE(professor_name)
            )
        """)
        conn.commit()
        conn.close()
    
    def setup_outlook(self):
        """Setup connection to Outlook client"""
        try:
            self.outlook = win32com.client.Dispatch('Outlook.Application')
            # Test the connection
            test = self.outlook.CreateItem(0)
            test = None
        except Exception as e:
            print("Please make sure Outlook is running and try again.")
            raise ValueError("Could not connect to Outlook. Is it installed and running?")
    
    def check_databases(self):
        """Check the existence and content of required databases"""
        # Check validated_emails.db
        if not self.validated_db.exists():
            raise FileNotFoundError(f"validated_emails.db not found at {self.validated_db}")
        
        # Check professors.db for email addresses
        # Update path to use parent directory structure
        self.prof_db = Path(__file__).parent.parent / 'databases' / 'uoft_professors.db'
        if not self.prof_db.exists():
            raise FileNotFoundError(f"professors database not found at {self.prof_db}")
        
        try:
            # Check validated emails
            conn = sqlite3.connect(self.validated_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM validated_emails")
            validated_count = cursor.fetchone()[0]
            conn.close()
            
            # Check professor emails
            conn = sqlite3.connect(self.prof_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM professors WHERE email IS NOT NULL")
            prof_count = cursor.fetchone()[0]
            conn.close()
            
            print("\nDatabase Status:")
            print(f"- Found {validated_count} validated emails ready to send")
            print(f"- Found {prof_count} professors with email addresses")
            
            if validated_count == 0:
                raise ValueError("No validated emails found - run email_validator.py first")
            if prof_count == 0:
                raise ValueError("No professor emails found - check faculty_scraper.py output")
                
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Database error: {e}")
    
    def get_pending_emails(self) -> List[Dict]:
        """Get all validated emails that haven't been sent"""
        try:
            # First check if validated_emails table exists
            conn = sqlite3.connect(self.validated_db)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='validated_emails'
            """)
            
            if not cursor.fetchone():
                print("Error: validated_emails table not found")
                return []

            # Get all validated emails (without checking sent_emails table first)
            cursor.execute("""
                SELECT v.professor_name, v.validated_email, v.paper_title
                FROM validated_emails v
            """)
            
            validated_emails = cursor.fetchall()
            
            # Now check professor emails
            conn_prof = sqlite3.connect(self.prof_db)
            cursor_prof = conn_prof.cursor()
            cursor_prof.execute("SELECT name, email FROM professors")
            prof_emails = {name: email for name, email in cursor_prof.fetchall() if email}
            
            # Create list of emails that have professor email addresses
            emails = []
            for prof_name, content, paper_title in validated_emails:
                if prof_name in prof_emails:
                    emails.append({
                        'professor_name': prof_name,
                        'email': prof_emails[prof_name],
                        'content': content,
                        'paper_title': paper_title
                    })
                else:
                    print(f"Skipping {prof_name} - no email address found")
            
            return emails
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
            if 'conn_prof' in locals():
                conn_prof.close()
    
    def create_outlook_email(self, email_data: Dict) -> bool:
        """Create and display email in Outlook with retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        # Get paths to attachments
        template_dir = Path(__file__).parent.parent / 'templates'
        resume_path = template_dir / 'resume.pdf'
        transcript_path = template_dir / 'transcript.pdf'
        
        # Verify attachments exist
        if not resume_path.exists():
            print("Warning: resume.pdf not found in templates folder")
            return False
        if not transcript_path.exists():
            print("Warning: transcript.pdf not found in templates folder")
            return False
        
        for attempt in range(max_retries):
            try:
                # Try to reinitialize Outlook connection
                if attempt > 0:
                    print("Reconnecting to Outlook...")
                    self.outlook = win32com.client.Dispatch('Outlook.Application')
                
                mail = self.outlook.CreateItem(0)
                mail.To = email_data['email']
                mail.Subject = "Summer Undergraduate Research"
                
                # Add attachment mention if not present
                content = email_data['content']
                if "transcript and resume" not in content.lower():
                    content += "\n\nAttached are my transcript and resume."
                
                mail.Body = content
                
                # Add attachments
                mail.Attachments.Add(str(resume_path))
                mail.Attachments.Add(str(transcript_path))
                
                mail.Display()
                return True
                
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                else:
                    return False

    def review_and_send_emails(self):
        """Review and send emails with user confirmation"""
        pending_emails = self.get_pending_emails()
        
        if not pending_emails:
            print("No pending emails to send.")
            return
        
        print(f"\nFound {len(pending_emails)} emails to send.")
        print("\nMake sure Outlook is running before continuing.")
        input("Press Enter when ready to start...")
        
        for email in pending_emails:
            print(f"\nPreparing email for Professor {email['professor_name']}...")
            
            if self.create_outlook_email(email):
                choice = input("\nDid you send the email? (y/n/q): ").lower()
                
                if choice == 'q':
                    print("Exiting review process...")
                    return
                elif choice == 'y':
                    self.record_sent_email(email)
                    print(f"Recorded email as sent to {email['professor_name']}")
                    time.sleep(1)
                else:
                    print("Skipping this email...")
            else:
                print(f"Could not create email for {email['professor_name']}")
                choice = input("Continue to next email? (y/n): ").lower()
                if choice != 'y':
                    break
    
    def send_email(self, email_data: Dict):
        """Send individual email using Outlook desktop client"""
        try:
            mail = self.outlook.CreateItem(0)  # 0 = olMailItem
            mail.To = email_data['email']
            mail.Subject = "Research Opportunity Inquiry"
            mail.Body = email_data['content']
            
            
            mail.Send()
            
            return True
        except Exception as e:
            print(f"Error creating email: {e}")
            return False
    
    def record_sent_email(self, email_data: Dict):
        """Record sent email in database"""
        conn = sqlite3.connect(self.sent_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sent_emails 
            (professor_name, professor_email, email_content, status)
            VALUES (?, ?, ?, ?)
        """, (
            email_data['professor_name'],
            email_data['email'],
            email_data['content'],
            'sent'
        ))
        
        conn.commit()
        conn.close()

def main():
    try:
        sender = EmailSender()
        sender.review_and_send_emails()
    except KeyboardInterrupt:
        print("\nEmail sending process interrupted.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()