from llama_index.llms.openai import OpenAI
import os

def get_llm():
    return OpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.1,
    )
