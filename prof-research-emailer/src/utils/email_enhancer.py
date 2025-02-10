import os
from pathlib import Path
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
from google import genai
from google.genai import types
import time
import random
from tenacity import retry, stop_after_attempt, wait_exponential
import json

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

class EmailEnhancer:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.setup_database()
        self.load_student_info()
        
    def setup_database(self):
        """Initialize the databases"""
        db_dir = Path(__file__).parent.parent / 'databases'
        db_dir.mkdir(exist_ok=True)
        
        self.template_db = db_dir / 'templated_emails.db'
        self.enhanced_db = db_dir / 'gemmed_emails.db'
        
        # Setup enhanced emails database
        conn = sqlite3.connect(self.enhanced_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gemmed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT NOT NULL,
                department TEXT NOT NULL,
                original_email TEXT NOT NULL,
                enhanced_email TEXT NOT NULL,
                paper_title TEXT NOT NULL,
                verification_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(professor_name, department)
            )
        """)
        conn.commit()
        conn.close()

    def load_student_info(self):
        """Load student background information"""
        config_path = Path(__file__).parent.parent / 'config' / 'student_info.json'
        with open(config_path, 'r') as f:
            self.student_info = json.load(f)

    def get_templated_emails(self):
        """Fetch all unprocessed emails from templated_emails database"""
        try:
            conn = sqlite3.connect(self.template_db)
            cursor = conn.cursor()
            
            # First check if templated_emails exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templated_emails'")
            if not cursor.fetchone():
                print("No templated_emails table found. Please generate emails first.")
                return []
            
            # Get all emails from templated_emails
            cursor.execute("""
                SELECT professor_name, department, email_content 
                FROM templated_emails
            """)
            emails = cursor.fetchall()
            
            # Now check gemmed_emails for already processed ones
            conn_gemmed = sqlite3.connect(self.enhanced_db)
            cursor_gemmed = conn_gemmed.cursor()
            
            cursor_gemmed.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gemmed_emails'")
            if cursor_gemmed.fetchone():
                # If gemmed_emails exists, filter out processed ones
                cursor_gemmed.execute("SELECT professor_name FROM gemmed_emails")
                processed_profs = {row[0] for row in cursor_gemmed.fetchall()}
                emails = [email for email in emails if email[0] not in processed_profs]
            
            conn_gemmed.close()
            return emails
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
        finally:
            conn.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _make_api_request(self, prompt: str, max_tokens: int = 500, temp: float = 0.1) -> str:
        """Make API request with retry logic"""
        try:
            # Add random delay between requests
            time.sleep(random.uniform(1.0, 2.0))
            
            response = self.client.models.generate_content(
                model="gemini-pro",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temp
                )
            )
            return response.text
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e):
                print("API rate limit reached. Waiting before retry...")
                time.sleep(60)  # Wait 60 seconds before retry
                raise  # Let retry decorator handle it
            raise

    def verify_and_enhance(self, professor_name: str, department: str, original_email: str) -> dict:
        """Verify professor and enhance email using Gemini"""
        try:
            verification_prompt = f"""
            Task 1 - Verify Professor at UofT:
            1. Check if {professor_name} is currently a professor in the {department} department at University of Toronto
            2. Find their most relevant and recent publication from UofT-affiliated work
            3. Return in format:
            VERIFIED: [True/False]
            PUBLICATION: [Title of verified recent paper]
            NOTES: [Verification details]
            """

            verify_text = self._make_api_request(verification_prompt)
            
            # Parse verification response
            is_verified = "VERIFIED: True" in verify_text
            paper_title = verify_text.split("PUBLICATION:")[1].split("\n")[0].strip() if "PUBLICATION:" in verify_text else ""
            notes = verify_text.split("NOTES:")[1].strip() if "NOTES:" in verify_text else ""

            if not is_verified:
                return {
                    "success": False,
                    "message": f"Verification failed: {notes}"
                }

            # Enhanced email generation with longer wait
            time.sleep(2)  # Additional delay between requests
            
            enhance_prompt = f"""
            Task: Enhance this research opportunity email for Professor {professor_name} at UofT.
            
            About the student:
            - Name: {self.student_info['name']}
            - Program: {self.student_info['program']}
            - Year: {self.student_info['year']}
            - Current relevant courses: {', '.join(self.student_info['relevant_courses'])}
            - Technical skills: {', '.join(self.student_info['technical_skills'])}
            - Projects: {json.dumps(self.student_info['projects'], indent=2)}
            - Research interests: {', '.join(self.student_info['research_interests'])}

            Original email:
            {original_email}
            
            Instructions:
            1. Research their current projects from UofT website
            2. Reference their recent work: "{paper_title}"
            3. Make connections between the student's actual background and the professor's research
            4. Be honest about the student's level of experience (first-year undergraduate)
            5. Show enthusiasm and willingness to learn
            6. Maintain professional tone while being authentic
            7. Focus on potential to contribute and learn rather than existing expertise
            8. Only mention skills and experiences listed in the student background
            
            Return only the enhanced email text.
            """

            enhanced_email = self._make_api_request(
                enhance_prompt, 
                max_tokens=1000, 
                temp=0.2
            )

            return {
                "success": True,
                "enhanced_email": enhanced_email,
                "paper_title": paper_title,
                "notes": notes
            }
            
        except Exception as e:
            print(f"Error processing {professor_name}: {str(e)}")
            return {
                "success": False,
                "message": f"Processing failed: {str(e)}"
            }

    def process_all_emails(self):
        """Process all unprocessed emails from template database"""
        templated_emails = self.get_templated_emails()
        results = []

        for prof_name, department, original_email in templated_emails:
            print(f"\nProcessing email for: {prof_name}")
            
            result = self.verify_and_enhance(prof_name, department, original_email)
            
            if result["success"]:
                # Save to database
                conn = sqlite3.connect(self.enhanced_db)
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO gemmed_emails 
                        (professor_name, department, original_email, enhanced_email, 
                         paper_title, verification_notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        prof_name, department, original_email,
                        result["enhanced_email"], result["paper_title"],
                        result["notes"]
                    ))
                    conn.commit()
                    print(f"Enhanced email saved for: {prof_name}")
                except Exception as e:
                    print(f"Error saving email: {str(e)}")
                finally:
                    conn.close()
            else:
                print(f"Failed to process email for {prof_name}: {result['message']}")
            
            results.append((prof_name, result))
        
        return results

def main():
    """Main function to process all emails"""
    enhancer = EmailEnhancer()
    results = enhancer.process_all_emails()
    
    print("\nProcessing Summary:")
    print("=" * 50)
    for prof_name, result in results:
        status = "Success" if result["success"] else "Failed"
        print(f"{prof_name}: {status}")

if __name__ == "__main__":
    main()