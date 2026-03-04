import logging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

# Desactivado: No se genera ni se carga modelo de embeddings
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384

async def generate_embedding(text: str) -> list[float]:
    LOGGER.info("Embedding generation is disabled. Returning None.")
    return None
