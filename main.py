from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return {"status": "ok", "message": "Minimal backend working!"}, 200

@app.route('/ping')
def ping():
    return "pong"

if __name__ == '__main__':
    print("🚀 Starting minimal Flask app...")
    app.run(host='0.0.0.0', port=8080, debug=True)