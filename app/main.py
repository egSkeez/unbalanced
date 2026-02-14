
import sys
import os

# Add the parent directory (project root) to sys.path so we can import from the root modules (api.py, etc.)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the FastAPI instance from the root api.py
# If Render tries to run 'uvicorn app.main:app', this file will satisfy that import path.
from api import app
