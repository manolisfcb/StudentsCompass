from sentence_transformers import SentenceTransformer
import logging
import asyncio
from typing import List
from concurrent.futures import ThreadPoolExecutor
import os

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)

# Thread pool for CPU-bound embedding generation
_embedding_executor = ThreadPoolExecutor(max_workers=3)

# Modelo de embeddings - se carga una vez y se reutiliza
_model = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384

# Keep compatibility with users setting only HUGGINGFACE_HUB_TOKEN in .env.
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
if HF_TOKEN and not os.getenv("HF_TOKEN"):
    os.environ["HF_TOKEN"] = HF_TOKEN


def _get_model():
    """Lazy load del modelo de embeddings."""
    global _model
    if _model is None:
        LOGGER.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME, token=HF_TOKEN)
    return _model


def _generate_embedding_sync(text: str) -> List[float]:
    """Genera embedding de forma síncrona usando sentence-transformers."""
    model = _get_model()
    # Limitar el texto a un tamaño razonable (ej. primeros 5000 caracteres)
    text = text[:5000] if len(text) > 5000 else text
    
    if not text.strip():
        LOGGER.warning("Empty text provided for embedding generation")
        return [0.0] * EMBEDDING_DIMS
    
    try:
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        LOGGER.error(f"Error generating embedding: {e}")
        raise


async def generate_embedding(text: str) -> List[float]:
    """
    Genera un embedding para el texto dado de forma asíncrona.
    
    Args:
        text: Texto del resume
        
    Returns:
        Lista de floats con el embedding (384 dimensiones)
    """
    loop = asyncio.get_event_loop()
    try:
        embedding = await loop.run_in_executor(_embedding_executor, _generate_embedding_sync, text)
        LOGGER.info(f"Generated embedding with {len(embedding)} dimensions")
        return embedding
    except Exception as e:
        LOGGER.error(f"Failed to generate embedding: {e}")
        raise
