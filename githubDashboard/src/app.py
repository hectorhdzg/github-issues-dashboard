from flask import Flask, render_template
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
           template_folder="../templates",
           static_folder="../static")

@app.route("/")
def index():
    return render_template("dashboard.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    print(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
