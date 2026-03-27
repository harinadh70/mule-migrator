"""
Main blueprint — Dashboard page and health check.
"""
from flask import Blueprint, render_template, jsonify
import os

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def dashboard():
    return render_template('dashboard.html')


@main_bp.route('/api/health', methods=['GET'])
def health():
    from flask import current_app
    return jsonify({"status": "ok", "env": current_app.config.get("ENV", "production")})
