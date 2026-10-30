from functools import wraps
import time
from flask import session, redirect, url_for, request, flash, jsonify
from config import Config

# Simple memory-based IP rate limiter for login
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes

def is_rate_limited(ip):
    now = time.time()
    attempts, lock_until = LOGIN_ATTEMPTS.get(ip, (0, 0))
    if lock_until > now:
        return True, int(lock_until - now)
    return False, 0

def record_failed_attempt(ip):
    now = time.time()
    attempts, lock_until = LOGIN_ATTEMPTS.get(ip, (0, 0))
    attempts += 1
    if attempts >= MAX_ATTEMPTS:
        LOGIN_ATTEMPTS[ip] = (0, now + LOCKOUT_SECONDS)
    else:
        LOGIN_ATTEMPTS[ip] = (attempts, 0)

def reset_attempts(ip):
    if ip in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[ip]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized", "message": "Please log in to continue."}), 401
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function
