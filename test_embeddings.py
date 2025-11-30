#!/usr/bin/env python3
"""
Test script to verify embeddings are working
"""
from ollama_client import OllamaClient

def test_embeddings():
    print("Testing Ollama Embeddings...")
    print("="*80)
    
    client = OllamaClient()
    
    # Test 1: Check connection
    print("\n1. Checking Ollama connection...")
    if client.check_connection():
        print("   ✓ Ollama is running")
        print(f"   ✓ Model: {client.model}")
    else:
        print("   ✗ Ollama not available or model not found")
        print(f"   → Run: ollama pull {client.model}")
        return
    
    # Test 2: Small text
    print("\n2. Testing with small text...")
    small_text = "This is a test mapping from User to UserDTO"
    embedding = client.get_embeddings(small_text)
    if embedding:
        print(f"   ✓ Success! Embedding dimension: {len(embedding)}")
    else:
        print("   ✗ Failed to get embedding")
    
    # Test 3: Medium text
    print("\n3. Testing with medium text (1000 chars)...")
    medium_text = "A" * 1000
    embedding = client.get_embeddings(medium_text)
    if embedding:
        print(f"   ✓ Success! Embedding dimension: {len(embedding)}")
    else:
        print("   ✗ Failed to get embedding")
    
    # Test 4: Large text
    print("\n4. Testing with large text (10000 chars)...")
    large_text = "B" * 10000
    embedding = client.get_embeddings(large_text)
    if embedding:
        print(f"   ✓ Success! Embedding dimension: {len(embedding)}")
    else:
        print("   ✗ Failed to get embedding")
    
    # Test 5: Very large text (should truncate)
    print("\n5. Testing with very large text (50000 chars, should truncate)...")
    very_large_text = "C" * 50000
    embedding = client.get_embeddings(very_large_text)
    if embedding:
        print(f"   ✓ Success! Embedding dimension: {len(embedding)}")
    else:
        print("   ✗ Failed to get embedding")
    
    print("\n" + "="*80)
    print("Test Complete")

if __name__ == '__main__':
    test_embeddings()

