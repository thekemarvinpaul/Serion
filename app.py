"""
Serion's web app — the simulated Alexa+ experience.

Run with: python app.py
Then open http://127.0.0.1:5000
"""

from flask import Flask, render_template, request, jsonify

from agent.agent import build_agent, ask_with_retry
from ledger.db import init_db
from ledger import models, ballots

app = Flask(__name__)

init_db()
agent = build_agent()  # one shared agent for the whole session


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/members")
def api_members():
    cycle_id = models.get_current_cycle_id()
    return jsonify(models.get_cycle_members(cycle_id))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    member = (data.get("member") or "").strip()
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"reply": ""})

    prefixed = f"[Speaking as {member}] {message}" if member else message
    reply = ask_with_retry(agent, prefixed)
    return jsonify({"reply": reply})


@app.route("/api/status")
def api_status():
    cycle_id = models.get_current_cycle_id()
    return jsonify(models.get_status(cycle_id))


@app.route("/api/forecast")
def api_forecast():
    receiver = request.args.get("receiver", "")
    cycle_id = models.get_current_cycle_id()
    return jsonify(models.forecast_payout(cycle_id, receiver))


@app.route("/api/confirm", methods=["POST"])
def api_confirm():
    """
    Direct confirm action — bypasses the agent entirely. Confirming
    a specific claim is a constrained, repetitive action (not
    something that benefits from natural language), so it's a button
    in the UI rather than a chat message.
    """
    data = request.get_json(force=True)
    claim_id = data.get("claim_id")
    member = (data.get("member") or "").strip()
    confirmed_amount = data.get("confirmed_amount")
    result = models.confirm_payment(claim_id, member, confirmed_amount)
    return jsonify(result)


@app.route("/api/vote", methods=["POST"])
def api_vote():
    """Direct vote action — same reasoning as /api/confirm above."""
    data = request.get_json(force=True)
    ballot_id = data.get("ballot_id")
    member = (data.get("member") or "").strip()
    choice = data.get("choice", "")
    result = ballots.cast_ballot(ballot_id, member, choice)
    return jsonify(result)


@app.route("/api/ballot")
def api_ballot():
    ballot_id = request.args.get("id", type=int)
    cycle_id = models.get_current_cycle_id()
    if not ballot_id:
        return jsonify({"error": "Enter a ballot number."})
    return jsonify(ballots.get_ballot_result(ballot_id, cycle_id))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
