import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Ensure correct API port is set before streamlit imports anything
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:5000")

from streamlit.web import cli as stcli

sys.argv = ["streamlit", "run", "dashboard/app.py", "--server.port", "8501"]
sys.exit(stcli.main())

