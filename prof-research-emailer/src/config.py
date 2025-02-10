import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration settings for the project
DATABASE_DIR = os.path.join(os.path.dirname(__file__), 'databases')
DATABASE_NAME = "uoft_professors.db"
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')