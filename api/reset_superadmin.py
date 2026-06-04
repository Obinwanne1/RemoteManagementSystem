"""
Emergency CLI: reset the superadmin password.
Usage:
    python reset_superadmin.py <new_password>

Run from the api/ directory. Minimum 10 characters.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from extensions import db
from models.user import User
from utils.superadmin import SUPERADMIN_EMAIL, SUPERADMIN_NAME, ensure_superadmin

if len(sys.argv) != 2:
    print("Usage: python reset_superadmin.py <new_password>")
    sys.exit(1)

new_password = sys.argv[1]
if len(new_password) < 10:
    print("Error: password must be at least 10 characters")
    sys.exit(1)

app = create_app()
with app.app_context():
    ensure_superadmin()
    sa = User.query.filter_by(email=SUPERADMIN_EMAIL).first()
    sa.set_password(new_password)
    sa.is_active = True
    sa.must_change_password = False
    db.session.commit()
    print(f"Superadmin password reset.")
    print(f"  Email: {SUPERADMIN_EMAIL}")
    print(f"  Login at http://localhost:8501")
