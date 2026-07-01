import uuid
from flask import Flask, request, jsonify
from signals import get_llm_signal
from logger import add_log_entry, get_log

app = Flask(__name__)

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    text = data.get("text")
    creator_id = data.get("creator_id")

    content_id = str(uuid.uuid4())

    llm_score = get_llm_signal(text)

    # Placeholder logic — real combined scoring comes in Milestone 4
    confidence = llm_score
    attribution = "likely_ai" if llm_score >= 0.5 else "likely_human"
    label = f"[Placeholder] Attribution: {attribution}, confidence: {confidence}"

    add_log_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
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