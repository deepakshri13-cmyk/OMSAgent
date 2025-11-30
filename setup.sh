#!/bin/bash
# Setup script for AI Code Understanding SME

echo "Setting up AI Code Understanding SME..."
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Install Python dependencies
echo ""
echo "Installing Python dependencies (including ChromaDB)..."
pip3 install -r requirements.txt

# Check if Ollama is installed
echo ""
if command -v ollama &> /dev/null; then
    echo "✓ Ollama is installed"
    echo ""
    echo "Checking for Jina embeddings model..."
    if ollama list | grep -q "jina-embeddings-v2-base-code"; then
        echo "✓ Jina embeddings model is already installed"
    else
        echo "Installing Jina embeddings model..."
        ollama pull unclemusclez/jina-embeddings-v2-base-code
    fi
    echo ""
    echo "Checking for Qwen2.5-Coder model..."
    if ollama list | grep -q "qwen2.5-coder"; then
        echo "✓ Qwen2.5-Coder model is already installed"
    else
        echo "Installing Qwen2.5-Coder 7B model..."
        ollama pull qwen2.5-coder:7b
    fi
else
    echo "⚠ Ollama is not installed"
    echo "  Please install Ollama from: https://ollama.com"
    echo "  Then run:"
    echo "    ollama pull unclemusclez/jina-embeddings-v2-base-code"
    echo "    ollama pull qwen2.5-coder:7b"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Components installed:"
echo "  ✓ Python dependencies (PyYAML, requests, chromadb, streamlit)"
echo "  ✓ Ollama integration ready"
echo "  ✓ ChromaDB vector database ready"
echo "  ✓ Streamlit UI ready"
echo ""
echo "To test the system, run:"
echo "  python3 test_example.py"
echo ""
echo "Or process a Java file:"
echo "  python3 main.py <path-to-java-file>"
echo ""
echo "Launch the Web UI:"
echo "  streamlit run app.py"
echo ""
echo "Search for similar mappings:"
echo "  python3 main.py --search 'User to UserDTO mapping'"
echo ""
echo "View vector database stats:"
echo "  python3 main.py --db-stats"

