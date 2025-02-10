import os
from pathlib import Path
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
from google import genai
from google.genai import types
from scholarly import scholarly
import time
import random
from tenacity import retry, stop_after_attempt, wait_exponential
import json

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

class EmailValidator:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.setup_database()
        self.load_student_info()
        
    def setup_database(self):
        """Initialize the databases"""
        db_dir = Path(__file__).parent.parent / 'databases'
        self.enhanced_db = db_dir / 'gemmed_emails.db'
        self.validated_db = db_dir / 'validated_emails.db'
        
        # Setup validated emails database
        conn = sqlite3.connect(self.validated_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validated_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT NOT NULL,
                department TEXT NOT NULL,
                original_email TEXT NOT NULL,
                enhanced_email TEXT NOT NULL,
                validated_email TEXT NOT NULL,
                paper_title TEXT NOT NULL,
                paper_verification TEXT,
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

    def verify_publication(self, professor_name: str, paper_title: str) -> dict:
        """Verify publication using Google Scholar"""
        try:
            search_query = scholarly.search_author(professor_name)
            author = next(search_query)
            author_filled = scholarly.fill(author, sections=['publications'])
            
            # Check if paper exists in professor's publications
            for pub in author_filled['publications']:
                if paper_title.lower() in pub['bib']['title'].lower():
                    return {
                        "verified": True,
                        "paper": pub['bib']['title'],
                        "year": pub['bib'].get('pub_year', 'N/A'),
                        "url": pub.get('pub_url', '')
                    }
            
            # If paper not found, get most recent relevant publication
            recent_pub = author_filled['publications'][0]['bib']
            return {
                "verified": False,
                "suggested_paper": recent_pub['title'],
                "year": recent_pub.get('pub_year', 'N/A'),
                "url": recent_pub.get('pub_url', '')
            }
            
        except Exception as e:
            print(f"Error verifying publication: {e}")
            return {"verified": False, "error": str(e)}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def validate_and_improve_email(self, professor_name: str, department: str, 
                                 original_email: str, enhanced_email: str, 
                                 paper_title: str) -> dict:
        """Validate and improve the enhanced email"""
        # Verify publication first
        pub_info = self.verify_publication(professor_name, paper_title)
        
        validation_prompt = f"""
        Task: Write a research opportunity email that is STRICTLY based on the student's actual background.

        Professor Information:
        Name: {professor_name}
        Department: {department}
        Verified Paper: {pub_info.get('paper') or pub_info.get('suggested_paper')}
        Year: {pub_info.get('year', 'N/A')}

        Student's EXACT Background:
        1. Program: {self.student_info['program']}
        2. Year: {self.student_info['year']}
        3. Actual Courses (only these):
        {', '.join(self.student_info['relevant_courses'])}
        4. Verified Technical Skills (only these):
        {', '.join(self.student_info['technical_skills'])}
        5. Real Projects:
        {json.dumps(self.student_info['projects'], indent=2)}
        6. Actual Awards:
        {json.dumps(self.student_info['awards'], indent=2)}
        
        Rough draft 1:{original_email}
        
        Rought draft 2:{enhanced_email}

        STRICT REQUIREMENTS:
        1. ONLY mention the verified paper title: "{pub_info.get('paper') or pub_info.get('suggested_paper')}"
        2. DO NOT invent or assume any skills/experience not listed above
        3. BE HONEST about being a first-year student
        4. MAINTAIN a humble, learning-focused tone
        5. INCLUDE the exact email: kev.peng@mail.utoronto.ca
        6. END with: "Please let me know if you have any opportunities in your lab. I can be reached at kev.peng@mail.utoronto.ca"

        EMAIL STRUCTURE:
        1. [First Paragraph] 
           - Introduce yourself (Kevin Peng) as a first-year student
           - State your program (Engineering Science)
        
        2. [Second Paragraph]
           - Reference the EXACT paper title
           - Express genuine interest in learning about this research
        
        3. [Third Paragraph]
           - List ONLY relevant courses and skills from above
           - Be explicit about being in a learning phase
        
        4. [Final Paragraph]
           - Express enthusiasm to learn
           - Include contact information
           - End with: "Please let me know if you have any opportunities in your lab. I can be reached at kev.peng@mail.utoronto.ca"

        CRITICAL RULES:
        - NO hypothetical scenarios
        - NO claims about research contributions
        - NO skills or experiences not listed above
        - COPY the paper title exactly as provided
        - MAINTAIN a humble, learning-focused tone
        - BE EXPLICIT about first-year status
        - VERIFY every statement against the provided background

        Format: Return ONLY the email text, no other text or explanations.
        """

        try:
            time.sleep(random.uniform(1.0, 2.0))
            
            response = self.client.models.generate_content(
                model="gemini-pro",
                contents=[validation_prompt],
                config=types.GenerateContentConfig(
                    max_output_tokens=1000,
                    temperature=0.1  # Keep temperature low for consistency
                )
            )
            
            # Verify the generated email
            if not self._verify_email_content(response.text, 
                pub_info.get('paper') or pub_info.get('suggested_paper')):
                raise ValueError("Generated email failed verification checks")
            
            return {
                "success": True,
                "validated_email": response.text,
                "paper_info": pub_info
            }
            
        except Exception as e:
            print(f"Error validating email: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _verify_email_content(self, email_text: str, paper_title: str) -> bool:
        """Verify the generated email follows all rules"""
        checks = [
            paper_title in email_text,  # Correct paper title
            "first-year" in email_text.lower(),  # Mentions first-year status
            "kev.peng@mail.utoronto.ca" in email_text,  # Contains email
            "Please let me know if you have any opportunities in your lab" in email_text  # Contains required closing
        ]
        return all(checks)

    def process_enhanced_emails(self):
        """Process all enhanced emails"""
        try:
            conn = sqlite3.connect(self.enhanced_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT professor_name, department, original_email, 
                       enhanced_email, paper_title
                FROM gemmed_emails
            """)
            enhanced_emails = cursor.fetchall()
            conn.close()
            
            for email in enhanced_emails:
                prof_name, dept, orig, enhanced, paper = email
                print(f"\nValidating email for: {prof_name}")
                
                result = self.validate_and_improve_email(
                    prof_name, dept, orig, enhanced, paper
                )
                
                if result["success"]:
                    # Save validated email
                    conn = sqlite3.connect(self.validated_db)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO validated_emails 
                        (professor_name, department, original_email, 
                         enhanced_email, validated_email, paper_title, 
                         paper_verification)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        prof_name, dept, orig, enhanced,
                        result["validated_email"],
                        result["paper_info"].get('paper') or 
                        result["paper_info"].get('suggested_paper'),
                        json.dumps(result["paper_info"])
                    ))
                    conn.commit()
                    conn.close()
                    print(f"Validated email saved for: {prof_name}")
                    
        except Exception as e:
            print(f"Error processing emails: {e}")

def main():
    validator = EmailValidator()
    validator.process_enhanced_emails()

if __name__ == "__main__":
    main()