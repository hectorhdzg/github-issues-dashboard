#
# Combined deployment of both Dashboard and Sync Service
# This creates a single app that serves both the frontend and the API

import os
import sys
from flask import Flask, render_template, send_from_directory

# Import the sync service
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'githubSync', 'src'))

try:
    from app import app as sync_app, GitHubSyncService
    print("Successfully imported sync service")
except ImportError as e:
    print(f"Failed to import sync service: {e}")
    sync_app = None

# Create the combined Flask app
app = Flask(__name__, 
           template_folder="../templates",
           static_folder="../static")

# Copy all routes from sync service if available
if sync_app:
    # Copy all sync service routes to our app
    for rule in sync_app.url_map.iter_rules():
        endpoint = rule.endpoint
        if endpoint != 'static':  # Don't copy static file routes
            view_func = sync_app.view_functions[endpoint]
            app.add_url_rule(rule.rule, endpoint, view_func, methods=rule.methods)
    print("Sync service routes added to combined app")

# Dashboard routes
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/dashboard")
def dashboard_alt():
    return render_template("dashboard.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    print(f"Starting combined GitHub Dashboard + Sync Service on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)