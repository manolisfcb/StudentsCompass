"""
Script de prueba para verificar la generación de embeddings
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.embeddingService import generate_embedding, MODEL_NAME, EMBEDDING_DIMS


async def test_embedding():
    """Prueba la generación de embeddings con texto de ejemplo"""
    
    test_text = """
    Software Engineer with 5 years of experience in Python, JavaScript, and cloud technologies.
    Expert in FastAPI, React, and AWS. Strong background in machine learning and data science.
    Experience with Docker, Kubernetes, and CI/CD pipelines.
    """
    
    print(f"Testing embedding generation with model: {MODEL_NAME}")
    print(f"Expected dimensions: {EMBEDDING_DIMS}")
    print(f"\nTest text ({len(test_text)} chars):")
    print(test_text[:100] + "...")
    
    try:
        print("\nGenerating embedding...")
        embedding = await generate_embedding(test_text)
        
        print(f"✅ Success!")
        print(f"Generated embedding with {len(embedding)} dimensions")
        print(f"Sample values: {embedding[:5]}")
        print(f"Min value: {min(embedding):.4f}")
        print(f"Max value: {max(embedding):.4f}")
        
        # Verificar que sea un vector normalizado (longitud ~1)
        import math
        norm = math.sqrt(sum(x*x for x in embedding))
        print(f"Vector norm: {norm:.4f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_embedding())
