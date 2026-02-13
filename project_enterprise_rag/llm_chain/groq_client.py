from groq import Groq
from dotenv import load_dotenv
import os
from pathlib import Path

# load .env
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY not loaded")

client = Groq(api_key=api_key)

def groq_complete(context: str, query: str) -> str:
    prompt = f"""
Answer the question using ONLY the context below.

Context:
{context}

Question:
{query}
"""

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # ✅ UPDATED MODEL
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return completion.choices[0].message.content
