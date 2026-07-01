import uuid
from flask import Flask, request, jsonify
from signals import get_llm_signal, get_stylometric_signal, get_confidence_score, get_label_category
from logger import add_log_entry, get_log

app = Flask(__name__)

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    content_id = str(uuid.uuid4())

    llm_score = get_llm_signal(text)
    stylo_score = get_stylometric_signal(text)
    confidence = get_confidence_score(llm_score, stylo_score)
    attribution = get_label_category(confidence)

    # Real label text comes in Milestone 5 — still a placeholder for now
    label = f"[Placeholder] Attribution: {attribution}, confidence: {confidence:.2f}"

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

@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": get_log()})

if __name__ == "__main__":
    app.run(debug=True, port=5000)