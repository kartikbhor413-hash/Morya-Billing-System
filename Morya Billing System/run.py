"""
Moraya Electric Billing System - Application Runner
"""
import os
from app import app
from config import Config

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting {Config.BUSINESS_NAME} Billing System on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
