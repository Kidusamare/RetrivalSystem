import os

# ======================================================================
# FIX GRADIO "schema True" BUG BEFORE ANY GRADIO IMPORTS
# ======================================================================
import gradio_client.utils as gu
from typing import Any

# Save originals only once
if not hasattr(gu, "_json_schema_to_python_type_original"):
    gu._json_schema_to_python_type_original = getattr(
        gu, "_json_schema_to_python_type", None
    )

if not hasattr(gu, "get_type_original"):
    gu.get_type_original = getattr(gu, "get_type", None)

# Patch get_type() – prevents schema=True crashes
def safe_get_type(schema):
    if isinstance(schema, bool):
        return None
    return gu.get_type_original(schema)

# Patch json->python schema conversion
def safe_json_schema_to_python_type(schema: Any, defs: Any = None):
    if isinstance(schema, bool):
        return None
    return gu._json_schema_to_python_type_original(schema, defs)

# Apply monkeypatch
if gu.get_type_original is not None:
    gu.get_type = safe_get_type
if gu._json_schema_to_python_type_original is not None:
    gu._json_schema_to_python_type = safe_json_schema_to_python_type

# ======================================================================
# Normal imports (safe now)
# ======================================================================
import gradio as gr
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 🚀 Disable ALL LLM calls globally (no OpenAI, no remote models)
from llama_index.core.settings import Settings
Settings.llm = None

# HuggingFace embedding model (local)
embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5",
    trust_remote_code=True,
    device="cpu"
)

vector_index = None


# ======================================================================
# LOAD FILE
# ======================================================================
def load_file(file_path: str):
    global vector_index
    if not file_path:
        return "Upload a file first."

    try:
        docs = SimpleDirectoryReader(input_files=[file_path]).load_data()

        vector_index = VectorStoreIndex.from_documents(
            docs,
            embed_model=embed_model
        )

        return f"Indexed: {os.path.basename(file_path)}"

    except Exception as e:
        return f"Error: {e}"


# ======================================================================
# ASK QUESTION (NO LLM, LOCAL EMBEDDING SEARCH ONLY)
# ======================================================================
def ask(question: str):
    global vector_index
    if not vector_index:
        return "Please upload and index a document first."

    try:
        qe = vector_index.as_query_engine(llm=None)   # Force NO LLM
        resp = qe.query(question)
        return resp.response

    except Exception as e:
        return f"Query error: {e}"


# ======================================================================
# UI
# ======================================================================
with gr.Blocks() as demo:
    gr.Markdown("# Document Q&A — Basic RAG (Project 1)")

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="Upload Document", type="filepath")
            btn = gr.Button("Index Document")
            status = gr.Textbox(label="Status")

        with gr.Column(scale=2):
            question = gr.Textbox(label="Ask a question")
            answer = gr.Textbox(label="Answer")

    btn.click(load_file, inputs=file_input, outputs=status)
    question.submit(ask, inputs=question, outputs=answer)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False,
        share=True
    )
