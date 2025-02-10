import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import re
import os

DEPARTMENT_CONFIGS = {
    "MIE": {
        "url": "https://www.mie.utoronto.ca/faculty/",
        "selector": lambda soup: [
            h5.get_text(strip=True) 
            for h5 in soup.find_all('h5', class_='pp-content-grid-title')
        ]
    },
    "Chemical": {
        "url": "https://chem-eng.utoronto.ca/faculty-staff/faculty-members/",
        "selector": lambda soup: [
            h2.a.get_text(strip=True) 
            for h2 in soup.find_all('h2', class_='fl-post-feed-title')
        ]
    },
    "MSE": {
        "url": "https://mse.utoronto.ca/faculty-staff/professors/",
        "selector": lambda soup: [
            link.get_text(strip=True)
            for div in soup.find_all('div', class_='fl-rich-text')
            for link in div.find_all('a', href=True)
            if 'professors' in link['href']
        ]
    },
    "BME": {
        "url": "https://bme.utoronto.ca/faculty-research/core-faculty/",
        "selector": lambda soup: [
            h3.get_text(strip=True)
            for div in soup.find_all('div', class_='awsm-personal-info')
            for h3 in div.find_all('h3')
        ]
    }
}

def scrape_professors():
    # Update database path to use src/databases
    db_path = os.path.join(os.path.dirname(__file__), '..', 'databases', 'uoft_professors.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Update table schema to include email
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS professors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT,
            UNIQUE(name, department)
        )
    """)
    
    for dept, config in DEPARTMENT_CONFIGS.items():
        print(f"\nScraping {dept} department from {config['url']}...")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124'
            }
            response = requests.get(config['url'], headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            names = config['selector'](soup)
            
            print(f"Found {len(names)} professors in {dept}")
            
            for name in names:
                if name:
                    # Clean up the name
                    name = re.sub(r'\s+', ' ', name).strip()
                    # Generate email (firstname.lastname@utoronto.ca)
                    email = None
                    name_parts = name.split()
                    if len(name_parts) >= 2:
                        email = f"{name_parts[0].lower()}.{name_parts[-1].lower()}@utoronto.ca"
                    
                    print(f"Processing: {name} ({email})")
                    cursor.execute("""
                        INSERT OR REPLACE INTO professors (name, department, email) 
                        VALUES (?, ?, ?)
                    """, (name, dept, email))
                    print(f"Added {name} from {dept} to database")
            
            conn.commit()
            time.sleep(1)  # Be nice to the servers
            
        except requests.RequestException as e:
            print(f"Error accessing {config['url']}: {e}")
        except Exception as e:
            print(f"Error processing {dept}: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    conn.close()
    print("\nFaculty scraping completed")

if __name__ == "__main__":
    scrape_professors()