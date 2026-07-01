import uuid
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from signals import get_llm_signal, get_stylometric_signal, get_confidence_score, get_label_category, get_label_text
from logger import add_log_entry, get_log, update_log_entry

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    content_id = str(uuid.uuid4())

    llm_score = get_llm_signal(text)
    stylo_score = get_stylometric_signal(text)
    confidence = round(get_confidence_score(llm_score, stylo_score), 2)
    attribution = get_label_category(confidence)
    label = get_label_text(confidence)

    add_log_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylo_score": stylo_score,
        "status": "classified"
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label
    })

@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "content_id and creator_reasoning are required"}), 400

    updated = update_log_entry(content_id, {
        "status": "under_review",
        "appeal_reasoning": creator_reasoning
    })

    if not updated:
        return jsonify({"error": f"No submission found with content_id {content_id}"}), 404

    return jsonify({
        "status": "under_review",
        "message": "Your appeal has been received and is under review."
    })

@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()})

if __name__ == "__main__":
    app.run(debug=True, port=5000)