# AI Code Understanding SME

An AI team member specialized in understanding Java code and extracting source-to-destination field-level mappings from MapStruct and POJO-based mapping code.

## Features

- **MapStruct Mapping Extraction**: Automatically detects and extracts field mappings from MapStruct mapper interfaces
- **POJO Mapping Extraction**: Identifies manual mapping methods in POJO classes
- **Configurable Input**: Supports single files, directories, or inline code input
- **Ollama Integration**: Uses embedding models (default: `nomic-embed-text`) for code understanding
- **On-Demand Mapping Extraction**: Extracts mappings from retrieved code when needed (faster ingestion)
- **Vector Database (ChromaDB)**: Stores embeddings for similarity search and knowledge base building
- **RAG (Retrieval-Augmented Generation)**: Ask questions about your code with intelligent answers
- **Web UI (Streamlit)**: Interactive interface for Q&A and code exploration
- **Qwen2.5-Coder 7B**: Uses Qwen2.5-Coder for code understanding and generation
- **Similarity Search**: Find similar mappings using semantic search
- **Multiple Output Formats**: JSON, YAML, or human-readable text

## Quick Start Guide

Follow these steps in order to set up and use the AI Code Understanding SME.

### Step 1: Prerequisites

#### 1.1 Install Python 3.8+
Ensure Python 3.8 or higher is installed:
```bash
python3 --version
```

Create Virtual Environment
``` bash
python3.11 -m venv .venv
source .venv/bin/activate
```


#### 1.2 Install Ollama
1. Download and install Ollama from: https://ollama.com
2. Start Ollama service:
   ```bash
   ollama serve
   ```
   (Keep this terminal open - Ollama must be running)

#### 1.3 Install Required Models
In a new terminal, pull the required models:
```bash
# Embeddings model (for code understanding) - recommended: nomic-embed-text
ollama pull nomic-embed-text
# Alternative: ollama pull unclemusclez/jina-embeddings-v2-base-code

# LLM model (for Q&A generation)
ollama pull qwen2.5-coder:7b
```

Verify models are installed:
```bash
ollama list
```

#### 1.4 Install Python Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- PyYAML (configuration)
- requests (Ollama API)
- chromadb (vector database)
- streamlit (web UI)
- tqdm (progress bars)

#### 1.5 Verify Setup
Check if everything is configured correctly:
```bash
python main.py --check-ollama
```

Expected output:
```
✓ Ollama is running and model 'nomic-embed-text' is available
```

---

### Step 2: Configure Your Codebase

Edit `config.yaml` to specify your Java project(s):

```yaml
input:
  projects:
    - "/path/to/your/java/project1"
    - "/path/to/your/java/project2"  # Optional: add up to 10 projects
  exclude_patterns:
    - "**/src/test/**"
    - "**/target/**"
    - "**/build/**"
    # ... other exclusions
```

**Important**: 
- Use absolute paths for project directories
- Each project can have 30k+ Java files
- Exclusion patterns help skip test files and build directories

---

### Step 3: Ingest Codebase to Vector Database

**This step must be completed before launching the UI.**

The ingestion process will:
1. Scan your Java projects
2. Extract mappings (MapStruct and POJO)
3. Generate embeddings for each mapping
4. Store everything in ChromaDB vector database

#### 3.1 Start Ingestion

```bash
python main.py --process-codebase
```

Or simply:
```bash
python main.py
```

#### 3.2 Monitor Progress

You'll see output like:
```
Found 30,000 Java file(s) (after exclusions)
Large codebase detected. Processing in chunks of 1,000 files...
Processing 30,000 files in 30 chunks of ~1,000 files each

Chunk 1/30: Processing files 1 to 1,000
Progress: 1,000/30,000 files (3.3%)
  ✓ Checkpoint: 1,000 files processed
  ✓ Stored 150 mapping(s) in vector database
...
```

**For large codebases (30k+ files):**
- Processing time: Several hours (depends on codebase size)
- Progress is saved incrementally to ChromaDB
- You can stop and resume (vector DB persists data)

#### 3.3 Verify Ingestion

Check how many mappings were stored:
```bash
python main.py --db-stats
```

Expected output:
```json
{
  "total_mappings": 5000,
  "mapping_types": {
    "mapstruct": 3000,
    "pojo": 2000
  },
  "collection_name": "code_mappings"
}
```

**If you see 0 mappings**, run the diagnostic tool:
```bash
python diagnose.py
```

This will check:
- Configuration (projects/paths)
- Ollama connection
- Vector database status
- File discovery
- Mapping extraction

**Note**: The ingestion process must complete successfully before you can use the UI for Q&A.

#### 3.4 Troubleshooting Ingestion Issues

**Problem: 0 mappings in database**

1. **Run diagnostic tool**:
   ```bash
   python diagnose.py
   ```

2. **Test a specific file**:
   ```bash
   python main.py --test-file path/to/your/Mapper.java
   ```

3. **Check if mappings are being extracted**:
   - Look for "✓ Stored X mapping(s)" messages during ingestion
   - If you see "⚠ No mappings found", the files may not contain MapStruct/POJO mappings

4. **Check Ollama connection**:
   ```bash
   python main.py --check-ollama
   ollama list  # Verify models are installed
   ```

5. **Enable verbose output**:
   ```bash
   python main.py --process-codebase --verbose
   ```

**Common Issues:**
- **No mappings found**: Files don't contain MapStruct or POJO mappings
- **Ollama not available**: Start Ollama service (`ollama serve`)
- **Embeddings failing**: Check Ollama logs, verify model is installed
- **Vector DB errors**: Check disk space, permissions on `./chroma_db` directory

---

### Step 4: Launch Web UI

**Only launch the UI after Step 3 (ingestion) is complete.**

#### 4.1 Start the UI

```bash
streamlit run app.py
```

Or use the convenience script:
```bash
./run_ui.sh
```

#### 4.2 Access the UI

The UI will open automatically in your browser at:
```
http://localhost:8501
```

If it doesn't open automatically, navigate to the URL manually.

#### 4.3 Using the UI

1. **Ask Questions Tab**: 
   - Enter questions about your code
   - Example: "Explain how UPC is mapped in SalesOrder and where all is it used?"
   - View retrieved context and AI-generated answers

2. **Database Stats Tab**:
   - View statistics about stored mappings
   - See mapping counts by type

3. **Search Mappings Tab**:
   - Semantic search for similar mappings
   - Find mappings by description

---

## Complete Workflow Summary

```
1. Install Prerequisites
   ├── Python 3.8+
   ├── Ollama
   ├── Pull models (jina-embeddings + qwen2.5-coder)
   └── Install Python dependencies

2. Configure config.yaml
   └── Set project paths

3. Ingest Codebase (REQUIRED FIRST)
   └── python main.py --process-codebase
   └── Wait for completion
   └── Verify with --db-stats

4. Launch UI (AFTER INGESTION)
   └── streamlit run app.py
   └── Ask questions about your code
```

---

## Troubleshooting

### Ingestion Issues

**Problem**: "Ollama not available"
```bash
# Solution: Make sure Ollama is running
ollama serve
```

**Problem**: "Model not found"
```bash
# Solution: Pull the missing model
ollama pull unclemusclez/jina-embeddings-v2-base-code
ollama pull qwen2.5-coder:7b
```

**Problem**: "Error getting embeddings: 500 - EOF" or embedding failures
```bash
# Solution 1: Test embeddings
python test_embeddings.py

# Solution 2: Verify the model supports embeddings
ollama show unclemusclez/jina-embeddings-v2-base-code

# Solution 3: Try a different embedding model
# Edit config.yaml and change:
# embeddings:
#   model: "nomic-embed-text"  # Alternative embedding model

# Solution 4: Restart Ollama
# Stop Ollama (Ctrl+C) and restart:
ollama serve

# Solution 5: Re-pull the model
ollama rm unclemusclez/jina-embeddings-v2-base-code
ollama pull unclemusclez/jina-embeddings-v2-base-code
```

**Note**: The default embedding model is now `nomic-embed-text` which is more stable than Jina. If you prefer Jina, update `config.yaml` and set `embeddings.model` to `"unclemusclez/jina-embeddings-v2-base-code"`.

**Problem**: Ingestion is very slow
- **Solution 1**: Increase parallelism settings in `config.yaml`:
  ```yaml
  input:
    parallel_workers: 6  # Increase from 4
    embedding_parallel_workers: 4  # Increase from 3
    max_concurrent_embedding_requests: 4  # Increase from 3
  ```
- **Solution 2**: Check exclusion patterns - ensure unnecessary files are excluded
- **Solution 3**: Process projects separately if system resources are limited
- **Solution 4**: Increase `file_chunk_size` for faster processing of very large codebases

**Problem**: "llama runner process no longer running" errors
- **Solution 1**: Reduce concurrent requests:
  ```yaml
  input:
    max_concurrent_embedding_requests: 2  # Reduce from 3
    embedding_parallel_workers: 2  # Reduce from 3
  ```
- **Solution 2**: Process fewer files in parallel:
  ```yaml
  input:
    parallel_workers: 2  # Reduce from 4
  ```
- **Solution 3**: Restart Ollama service

### Vector Database Management

#### Clear/Reset Vector Database

If you need to start fresh or clear corrupted data, you can reset the vector database:

**Option 1: Using CLI (Recommended)**
```bash
python main.py --clear-db
```
This will prompt for confirmation before deleting all mappings.

**Option 2: Delete Database Directory**
```bash
# Stop any running processes first
rm -rf ./chroma_db
```
The database will be recreated automatically on next ingestion.

**Option 3: Delete Specific Mappings**
If you need to delete mappings from a specific file:
```python
from main import CodeUnderstandingSME
sme = CodeUnderstandingSME()
if sme.vector_db:
    sme.vector_db.delete_by_file("/path/to/file.java")
```

**When to Clear the Database:**
- Starting fresh after configuration changes
- Corrupted or inconsistent data
- Need to re-ingest with different settings
- Testing with different codebases

**Note**: Clearing the database will require re-running ingestion (Step 3) before using the UI.

### UI Issues

**Problem**: "RAG service not available"
- **Solution**: Make sure you completed Step 3 (ingestion) first
- Check vector database has mappings: `python main.py --db-stats`

**Problem**: "No similar mappings found"
- **Solution**: Ingestion may not have completed or found mappings
- Re-run ingestion: `python main.py --process-codebase`

**Problem**: UI shows no projects
- **Solution**: Check `config.yaml` has correct project paths
- Verify paths exist and are accessible

## Advanced Configuration

Edit `config.yaml` to customize advanced settings:

### Input Configuration

```yaml
input:
  projects:
    - "/path/to/project1"
    - "/path/to/project2"  # Up to 10 projects
  exclude_patterns:
    - "**/src/test/**"
    - "**/target/**"
    - "**/build/**"
  # Performance settings for large codebases (30k+ files)
  embedding_batch_size: 50      # Batch size for embeddings
  parallel_workers: 4           # Parallel processing workers (file-level)
  embedding_parallel_workers: 3 # Parallel workers for embedding chunks within files
  max_concurrent_embedding_requests: 3  # Max concurrent requests to Ollama (prevents crashes)
  file_chunk_size: 1000         # Files per chunk (for 10k+ files)
  enable_checkpoint: true       # Enable progress checkpoints
  checkpoint_interval: 500      # Log progress every N files
```

### Other Configuration Options

- **Mapping detection**: MapStruct annotations, POJO patterns
- **Embeddings**: Model name, Ollama URL, enable/disable
- **Vector Database**: Persistence directory, collection name
- **LLM**: Model name, number of retrievals, streaming
- **Output**: Format (json/yaml/text), output file path

## Additional CLI Commands

### Process a single Java file:
```bash
python main.py path/to/Mapper.java
```

### Process a directory:
```bash
python main.py path/to/java/source/
```

### Process code from stdin:
```bash
cat Mapper.java | python main.py -
```

### Specify output format:
```bash
python main.py Mapper.java -f json -o mappings.json
```

### Search for similar mappings:
```bash
python main.py --search "User to UserDTO mapping"
```

### View vector database statistics:
```bash
python main.py --db-stats
```

## Example

Given a MapStruct mapper like:

```java
@Mapper
public interface UserMapper {
    @Mapping(source = "firstName", target = "name")
    @Mapping(source = "emailAddress", target = "email")
    UserDTO toDTO(User user);
}
```

The system will extract:
```json
{
  "file": "UserMapper.java",
  "mappings": [
    {
      "type": "mapstruct",
      "interface": "UserMapper",
      "method": "toDTO",
      "source_type": "User",
      "target_type": "UserDTO",
      "field_mappings": [
        {
          "source": "firstName",
          "target": "name"
        },
        {
          "source": "emailAddress",
          "target": "email"
        }
      ]
    }
  ]
}
```

## Architecture

- **`java_parser.py`**: Parses Java code using regex patterns to identify MapStruct and POJO mappings
- **`mapping_extractor.py`**: Extracts and structures field-level mappings
- **`ollama_client.py`**: Interfaces with Ollama API for embeddings and LLM generation
- **`vector_db.py`**: ChromaDB integration for storing and querying embeddings
- **`rag_service.py`**: RAG pipeline combining vector retrieval with LLM generation
- **`app.py`**: Streamlit web UI for interactive Q&A
- **`main.py`**: Main application and CLI interface
- **`config.yaml`**: Configuration file

## RAG Pipeline

The system uses a Retrieval-Augmented Generation (RAG) approach:

1. **User asks a question** (e.g., "Explain how UPC is mapped in SalesOrder")
2. **Question is embedded** using embedding model (default: nomic-embed-text)
3. **Similar code files are retrieved** from ChromaDB vector database
4. **Mappings are extracted on-demand** from retrieved code (if needed)
5. **Context is built** from retrieved code and extracted mappings
6. **Qwen2.5-Coder 7B generates answer** with reasoning and code snippets

This ensures answers are grounded in your actual codebase.

## Vector Database

The system uses **ChromaDB** to store embeddings of mappings, enabling:

- **Persistent Storage**: Mappings and their embeddings are stored locally
- **Similarity Search**: Find similar mappings using semantic search
- **Knowledge Base**: Build a knowledge base of mappings over time
- **Retrieval-Augmented Understanding**: Use stored mappings to enhance understanding of new code

The vector database is automatically initialized when processing files (if enabled in config). Embeddings are generated using the configured embedding model (default: nomic-embed-text) via Ollama and stored in ChromaDB for future queries. The system stores full code files, and mappings are extracted on-demand when code is retrieved for Q&A.

## Performance & Scalability

The system is optimized for large codebases with **multi-level parallel processing**:

### Parallel Processing Architecture

The system uses three levels of parallelism for optimal throughput:

1. **Project Level** (Top Level):
   - Multiple projects processed simultaneously
   - Limited to 2 projects at once to prevent system overload
   - Each project processes its files independently

2. **File Level** (Middle Level):
   - Files within a project processed in parallel
   - Configured via `parallel_workers` (default: 4)
   - Each file is read and prepared for embedding independently

3. **Chunk Level** (Bottom Level - Embedding):
   - Code chunks within large files embedded in parallel
   - Configured via `embedding_parallel_workers` (default: 3)
   - Multiple chunks embedded simultaneously for faster processing

4. **Rate Limiting** (Safety Layer):
   - Semaphore-based rate limiting prevents overwhelming Ollama
   - Configured via `max_concurrent_embedding_requests` (default: 3)
   - Ensures Ollama doesn't crash from too many concurrent requests

### Performance Features

- **Chunked Processing**: For 10k+ files, processes in configurable chunks (default: 1000 files/chunk)
- **Smart Exclusions**: Test files, build directories, and resources automatically excluded
- **Efficient Storage**: Vector database uses batch inserts for better performance
- **Progress Tracking**: Real-time progress bars and checkpoint logging
- **Memory Efficient**: Chunked processing prevents memory overflow on large codebases
- **Error Recovery**: Automatic retry with exponential backoff for failed embeddings
- **Tested**: Handles 30k+ Java files per project efficiently

### Performance Tuning Guide

#### Recommended Settings by System Type

**For Fast Systems (8+ CPU cores, 16GB+ RAM)**:
```yaml
input:
  parallel_workers: 6-8              # More files in parallel
  embedding_parallel_workers: 4      # More chunks in parallel
  max_concurrent_embedding_requests: 4  # More concurrent requests
```

**For Medium Systems (4-8 CPU cores, 8-16GB RAM)** - **Default**:
```yaml
input:
  parallel_workers: 4
  embedding_parallel_workers: 3
  max_concurrent_embedding_requests: 3
```

**For Slower Systems or if Ollama Crashes**:
```yaml
input:
  parallel_workers: 2                # Fewer files in parallel
  embedding_parallel_workers: 2      # Fewer chunks in parallel
  max_concurrent_embedding_requests: 2  # Fewer concurrent requests
```

#### Other Configuration Tips

**For Very Large Codebases (30k+ files per project)**:
- Set `file_chunk_size: 1000-5000` (processes files in chunks to manage memory)
- Enable `enable_checkpoint: true` for progress tracking
- Set `checkpoint_interval: 500` to log progress every N files
- Use exclusion patterns to skip unnecessary files (reduces processing time)

**If You Experience Ollama Crashes**:
- Reduce `max_concurrent_embedding_requests` to 2 or even 1
- Reduce `embedding_parallel_workers` to 2
- Reduce `parallel_workers` to 2-3
- Process projects one at a time instead of in parallel

**For Maximum Throughput** (if system is stable):
- Increase `max_concurrent_embedding_requests` to 4-5
- Increase `embedding_parallel_workers` to 4-5
- Increase `parallel_workers` to 6-8 (based on CPU cores)

## Limitations

- Regex-based parsing (not a full AST parser) - may miss complex cases
- Implicit MapStruct mappings require type analysis (placeholder implementation)
- POJO mapping detection relies on common method naming patterns
- Maximum 10 projects can be configured at once

## Future Enhancements

- Full AST parsing using JavaParser library
- Type inference for implicit mappings
- Support for more mapping frameworks
- Enhanced embedding-based code understanding
- Batch processing optimizations

## License

MIT

