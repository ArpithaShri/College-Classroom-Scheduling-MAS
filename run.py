"""Application entry point for College Classroom Scheduling System."""

import os
from config import config_by_name

# Simple entry point placeholder for Phase 1
if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    cfg = config_by_name.get(env, config_by_name["default"])
    print(f"College Classroom Scheduling System (MAS) - Starting in {env} mode")
