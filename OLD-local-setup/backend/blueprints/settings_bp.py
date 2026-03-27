"""
Settings blueprint — Settings page (all config stored client-side in localStorage).
"""
from flask import Blueprint, render_template

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings')
def settings_page():
    return render_template('settings.html')
