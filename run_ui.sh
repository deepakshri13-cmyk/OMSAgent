#!/bin/bash
# Quick script to run the Streamlit UI

echo "Starting AI Code Understanding SME Web UI..."
echo ""
echo "Make sure Ollama is running and models are installed:"
echo "  - unclemusclez/jina-embeddings-v2-base-code"
echo "  - qwen2.5-coder:7b"
echo ""
echo "The UI will open in your browser at http://localhost:8501"
echo ""

streamlit run app.py

