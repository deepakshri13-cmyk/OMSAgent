# Web UI Quick Start Guide

## Starting the UI

```bash
# Option 1: Using the run script
./run_ui.sh

# Option 2: Direct command
streamlit run app.py
```

The UI will open at `http://localhost:8501`

## Prerequisites

Before using the UI, ensure:

1. **Ollama is running**:
   ```bash
   ollama serve
   ```

2. **Models are installed**:
   ```bash
   ollama pull unclemusclez/jina-embeddings-v2-base-code
   ollama pull qwen2.5-coder:7b
   ```

3. **You have processed some Java files** (to populate the vector database):
   ```bash
   python main.py path/to/your/java/files/
   ```

## Using the UI

### 1. Ask Questions Tab

- Enter your question in the text area
- Adjust the number of retrievals (default: 5)
- Toggle streaming for real-time responses
- Click "Ask Question"

**Example Questions:**
- "Explain how UPC is mapped in SalesOrder and where all is it used?"
- "Show me all mappings from User to UserDTO"
- "What fields are mapped from Product to ProductDTO?"
- "Where is the email field transformed in the mapping?"

### 2. Database Stats Tab

- View statistics about stored mappings
- Click "Load All Mappings" to see all stored mappings
- Useful for understanding what's in your knowledge base

### 3. Search Mappings Tab

- Semantic search for similar mappings
- Enter a search query
- Adjust number of results
- View similarity scores and metadata

### 4. Sidebar Features

- **Configuration**: Check system status
- **Ollama Status**: Verify models are available
- **Vector DB**: View mapping counts
- **File Upload**: Process Java files directly in the UI

## How RAG Works

1. **Question Embedding**: Your question is converted to an embedding
2. **Vector Search**: Similar mappings are retrieved from ChromaDB
3. **Context Building**: Retrieved mappings are formatted as context
4. **LLM Generation**: Qwen2.5-Coder generates an answer with reasoning
5. **Response**: You see both the retrieved context and the generated answer

## Tips

- **Better Questions = Better Answers**: Be specific about what you want to know
- **More Retrievals**: Increase retrievals for complex questions (may be slower)
- **Streaming**: Enable streaming for real-time responses
- **Process Files First**: Make sure you've processed Java files before asking questions

## Troubleshooting

**"RAG service not available"**
- Check Ollama is running
- Verify vector database is enabled in config
- Process some Java files first

**"Model not found"**
- Run: `ollama pull qwen2.5-coder:7b`
- Check the model name in the sidebar

**No retrievals found**
- Process more Java files
- Try a different question
- Check vector database stats

