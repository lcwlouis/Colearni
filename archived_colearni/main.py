from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from knowledgeSearchingAgent.agent import (
    run_steps_1_4 as run_steps_1_4_agent,
    generate_step6_queries,
    extract_pois_and_insights,
    generate_quiz_from_extracted,
    ingest_extracted_after_pass,
    update_user_profile,
)


app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/step1_4/run")
def run_steps_1_4_api():
    payload = request.get_json() or {}
    topic = payload.get("topic", "")
    if not topic:
        return jsonify({"error": "Missing 'topic'"}), 400
    result = run_steps_1_4_agent(topic)
    return jsonify(result)


@app.post("/step6/queries")
def run_step6():
    payload = request.get_json() or {}
    selected_pois = payload.get("selected_pois", [])
    user_context = payload.get("user_context", {})
    output = generate_step6_queries(selected_pois, user_context)
    return jsonify({"markdown": output})


@app.post("/step8/extract")
def run_step8_extract():
    payload = request.get_json() or {}
    sources = payload.get("sources", [])
    user_context = payload.get("user_context", {})
    output = extract_pois_and_insights(sources, user_context)
    return jsonify({"markdown": output})


@app.post("/step9/quiz")
def run_step9_quiz():
    payload = request.get_json() or {}
    extracted_markdown = payload.get("extracted_markdown", "")
    output = generate_quiz_from_extracted(extracted_markdown)
    return jsonify({"markdown": output})


@app.post("/step10/ingest")
def run_step10_ingest():
    payload = request.get_json() or {}
    extracted_markdown = payload.get("extracted_markdown", "")
    quiz_result = payload.get("quiz_result", {})
    output = ingest_extracted_after_pass(extracted_markdown, quiz_result)
    return jsonify({"markdown": output})


@app.post("/step11/update_profile")
def run_step11_update_profile():
    payload = request.get_json() or {}
    feedback = payload.get("feedback", {})
    current_profile = payload.get("current_profile", {})
    output = update_user_profile(feedback, current_profile)
    return jsonify(output)


def main():
    app.run(host="0.0.0.0", port=5001)


if __name__ == "__main__":
    main()
