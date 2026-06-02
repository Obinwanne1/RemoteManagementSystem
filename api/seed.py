"""
Seed script — creates admin user, default customer, and built-in scripts.
Run once after migrations: python seed.py
"""
import sys
import os

# Ensure we're running from api/ directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from extensions import db
from models.user import User
from models.customer import Customer
from models.script import Script

ADMIN_EMAIL = "admin@rmm.local"
ADMIN_PASSWORD = "Admin1234!"
ADMIN_NAME = "RMM Administrator"

BUILTIN_SCRIPTS = [
    {
        "name": "Check Battery Health",
        "description": "Generate a battery health report",
        "file_type": "bat",
        "os_target": "windows",
        "content": open(
            os.path.join(os.path.dirname(__file__), "..", "scripts_library", "windows",
                         "check_battery_health.bat"),
            encoding="utf-8"
        ).read(),
    },
    {
        "name": "System Information",
        "description": "Collect and display system information",
        "file_type": "py",
        "os_target": "windows",
        "content": open(
            os.path.join(os.path.dirname(__file__), "..", "scripts_library", "windows",
                         "system_info.py"),
            encoding="utf-8"
        ).read(),
    },
    {
        "name": "Get Installed Software",
        "description": "List all installed software from registry",
        "file_type": "ps1",
        "os_target": "windows",
        "content": open(
            os.path.join(os.path.dirname(__file__), "..", "scripts_library", "windows",
                         "get_installed_software.ps1"),
            encoding="utf-8"
        ).read(),
    },
]


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        # Admin user
        existing = User.query.filter_by(email=ADMIN_EMAIL).first()
        if not existing:
            admin = User(
                email=ADMIN_EMAIL,
                full_name=ADMIN_NAME,
                role="admin",
            )
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            print(f"Created admin user: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        else:
            print(f"Admin user already exists: {ADMIN_EMAIL}")

        # Default customer
        default_customer = Customer.query.filter_by(slug="default").first()
        if not default_customer:
            default_customer = Customer(
                name="Default Organization",
                slug="default",
                email="contact@default.local",
                tier="standard",
            )
            db.session.add(default_customer)
            print("Created default customer: 'Default Organization'")
        else:
            print("Default customer already exists")

        # Built-in scripts
        for script_data in BUILTIN_SCRIPTS:
            existing_script = Script.query.filter_by(
                name=script_data["name"], is_builtin=True
            ).first()
            if not existing_script:
                script = Script(
                    name=script_data["name"],
                    description=script_data["description"],
                    file_type=script_data["file_type"],
                    os_target=script_data["os_target"],
                    content=script_data["content"],
                    is_builtin=True,
                )
                db.session.add(script)
                print(f"Created built-in script: {script_data['name']}")
            else:
                print(f"Script already exists: {script_data['name']}")

        db.session.commit()
        print("\nSeed complete!")
        print(f"Login at http://localhost:8501 with {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    seed()
