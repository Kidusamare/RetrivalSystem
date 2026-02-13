from llama_index.embeddings.mixedbreadai import MixedbreadAIEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import os
import logging

logging.basicConfig(level=logging.INFO)

def get_embedding_model():
    mxbai_key = os.getenv("MXBAI_API_KEY")

    # Try Mixedbread first (as per tutorial)
    if mxbai_key:
        try:
            logging.info("Trying Mixedbread embeddings...")
            return MixedbreadAIEmbedding(
                api_key=mxbai_key,
                model_name="mixedbread-ai/mxbai-embed-large-v1"
            )
        except Exception as e:
            logging.warning(f"Mixedbread failed: {e}")

    # Fallback (ENTERPRISE FIX)
    logging.info("Falling back to HuggingFace embeddings...")
    return HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
