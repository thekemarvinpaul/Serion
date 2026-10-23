"""
Day 1 checkpoint script for Serion.

Goal: prove that Strands + Gemini actually works end to end
before any Flask, any tools, or any ledger logic gets built.

Run with:  python test_agent.py
"""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.gemini import GeminiModel

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit(
        "No GEMINI_API_KEY found. Copy .env.example to .env "
        "and paste in your key from https://aistudio.google.com/apikey"
    )

model = GeminiModel(client_args={"api_key": api_key}, model_id="gemini-3.5-flash-lite")
agent = Agent(model=model)

if __name__ == "__main__":
    print("Asking the agent a test question...\n")
    response = agent("In one sentence, what is a rotating savings group?")
    print("\n--- Agent replied ---")
    print(response)
