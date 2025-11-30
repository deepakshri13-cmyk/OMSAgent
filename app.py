#!/usr/bin/env python3
"""
Streamlit UI for AI Code Understanding SME
"""
import streamlit as st
import yaml
from pathlib import Path
import json
import os

from main import CodeUnderstandingSME
from ollama_client import OllamaClient
from vector_db import VectorDatabase, CHROMADB_AVAILABLE
from rag_service import RAGService


# Page configuration
st.set_page_config(
    page_title="AI Code Understanding SME",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_sme(config_path: str = "config.yaml"):
    """Initialize the Code Understanding SME (cached)"""
    return CodeUnderstandingSME(config_path)


@st.cache_resource
def initialize_rag_service(_sme: CodeUnderstandingSME, llm_model: str = "qwen2.5-coder:7b"):
    """Initialize RAG service (cached)"""
    if not _sme.ollama_client or not _sme.vector_db:
        return None
    
    # Check if on-demand extraction is enabled
    extract_on_demand = _sme.config.get('embeddings', {}).get('extract_mappings_on_ingestion', False) == False
    
    return RAGService(
        ollama_client=_sme.ollama_client,
        vector_db=_sme.vector_db,
        llm_model=llm_model,
        extract_mappings_on_demand=extract_on_demand
    )


def main():
    # Header
    st.markdown('<div class="main-header">🔍 AI Code Understanding SME</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Ask questions about your code and get intelligent answers</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Load config
        config_path = st.text_input("Config File", value="config.yaml")
        
        # Initialize SME
        try:
            sme = initialize_sme(config_path)
            st.success("✓ System initialized")
        except Exception as e:
            st.error(f"Error initializing system: {e}")
            st.stop()
        
        # Check Ollama connection
        st.subheader("🔌 Ollama Status")
        if sme.ollama_client:
            if sme.ollama_client.check_connection():
                st.success("✓ Ollama connected")
            else:
                st.error("✗ Ollama not available")
                st.info("Run: ollama pull unclemusclez/jina-embeddings-v2-base-code")
        else:
            st.warning("Embeddings disabled")
        
        # Check LLM model
        llm_model = st.text_input("LLM Model", value="qwen2.5-coder:7b")
        if sme.ollama_client:
            if sme.ollama_client.check_llm_model(llm_model):
                st.success(f"✓ {llm_model} available")
            else:
                st.warning(f"⚠ {llm_model} not found")
                st.info(f"Run: ollama pull {llm_model}")
        
        # Vector DB status
        st.subheader("💾 Vector Database")
        if sme.vector_db:
            stats = sme.get_vector_db_stats()
            st.info(f"Total code files: {stats.get('total_code_files', 0)}")
            if stats.get('total_code_chunks', 0) > stats.get('total_code_files', 0):
                st.text(f"  Code chunks: {stats.get('total_code_chunks', 0)}")
            if stats.get('legacy_mappings', 0) > 0:
                st.text(f"  Legacy mappings: {stats.get('legacy_mappings', 0)} (from old ingestion)")
        else:
            st.warning("Vector DB not enabled")
        
        st.divider()
        
        # Codebase path configuration
        st.subheader("📁 Projects Configuration")
        projects = sme.config.get('input', {}).get('projects', [])
        codebase_path = sme.config.get('input', {}).get('codebase_path', '')
        
        if projects:
            st.info(f"Configured {len(projects)} project(s):")
            for i, project in enumerate(projects, 1):
                if Path(project).exists():
                    st.text(f"  {i}. ✓ {project}")
                else:
                    st.text(f"  {i}. ✗ {project} (not found)")
            
            if st.button("🔄 Process All Configured Projects"):
                with st.spinner("Processing projects..."):
                    results = sme.process_configured_codebase()
                    if results:
                        stored_count = sum(1 for r in results if r.get('summary', {}).get('code_stored', False))
                        st.success(f"✓ Processed {len(results)} file(s), stored {stored_count} code file(s)")
                    else:
                        st.error("Failed to process projects")
        elif codebase_path:
            st.info(f"Configured: `{codebase_path}`")
            if Path(codebase_path).exists():
                if st.button("🔄 Process Configured Codebase"):
                    with st.spinner("Processing codebase..."):
                        results = sme.process_configured_codebase()
                        if results:
                            stored_count = sum(1 for r in results if r.get('summary', {}).get('code_stored', False))
                            st.success(f"✓ Processed {len(results)} file(s), stored {stored_count} code file(s)")
                        else:
                            st.error("Failed to process codebase")
            else:
                st.warning(f"Path does not exist: {codebase_path}")
        else:
            st.info("No projects configured in config.yaml")
            st.text("Edit config.yaml to set 'projects' list")
        
        # Show exclusion patterns
        exclude_patterns = sme.config.get('input', {}).get('exclude_patterns', [])
        if exclude_patterns:
            with st.expander("🚫 Exclusion Patterns"):
                for pattern in exclude_patterns:
                    st.text(f"  • {pattern}")
        
        st.divider()
        
        # File upload
        st.subheader("📤 Upload Files")
        uploaded_file = st.file_uploader("Upload Java file", type=['java'])
        if uploaded_file:
            if st.button("Process Uploaded File"):
                with st.spinner("Processing file..."):
                    content = uploaded_file.read().decode('utf-8')
                    result = sme.process_content(content, uploaded_file.name)
                    st.success(f"Processed {uploaded_file.name}")
                    st.json(result.get('summary', {}))
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["💬 Ask Questions", "📊 Database Stats", "🔍 Search Code"])
    
    with tab1:
        st.header("Ask Questions About Your Code")
        st.markdown("""
        Ask questions like:
        - "Explain how UPC is mapped in SalesOrder and where all is it used?"
        - "Show me all mappings from User to UserDTO"
        - "What fields are mapped from Product to ProductDTO?"
        """)
        
        # Initialize RAG service
        rag_service = initialize_rag_service(sme, llm_model)
        
        if not rag_service:
            st.error("RAG service not available. Please ensure:")
            st.markdown("""
            - Ollama is running
            - Vector database is enabled
            - You have processed some Java files
            """)
            st.stop()
        
        # Question input
        question = st.text_area(
            "Your Question",
            placeholder="e.g., Explain how UPC is mapped in SalesOrder and where all is it used?",
            height=100
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            n_retrievals = st.number_input("Retrievals", min_value=1, max_value=20, value=5)
        with col2:
            use_streaming = st.checkbox("Stream response", value=True)
        
        if st.button("🔍 Ask Question", type="primary"):
            if not question:
                st.warning("Please enter a question")
            else:
                with st.spinner("Thinking..."):
                    if use_streaming:
                        # Get retrievals first for display
                        question_embedding = sme.ollama_client.get_embeddings(question)
                        retrievals = []
                        if question_embedding:
                            retrievals = sme.vector_db.search_similar(question_embedding, n_retrievals)
                        
                        # Show retrievals
                        with st.expander("📚 Retrieved Context", expanded=False):
                            if retrievals:
                                for i, ret in enumerate(retrievals, 1):
                                    st.markdown(f"**Retrieval {i}** (Similarity: {1 - ret.get('distance', 0):.2%})")
                                    st.json(ret.get('metadata', {}))
                                    st.text(ret.get('document', '')[:500])
                                    st.divider()
                            else:
                                st.info("No retrievals found")
                        
                        # Stream the answer
                        st.markdown("### 💡 Answer")
                        answer_placeholder = st.empty()
                        full_answer = ""
                        
                        try:
                            for chunk_data in rag_service.answer_question_streaming(question, n_retrievals):
                                if 'error' in chunk_data:
                                    st.error(chunk_data['error'])
                                    break
                                elif 'chunk' in chunk_data:
                                    full_answer += chunk_data['chunk']
                                    answer_placeholder.markdown(full_answer)
                                    if chunk_data.get('done', False):
                                        break
                            
                            if full_answer:
                                st.success("✓ Answer generated")
                        except Exception as e:
                            st.error(f"Error during streaming: {e}")
                    else:
                        # Non-streaming response
                        result = rag_service.answer_question(question, n_retrievals)
                        
                        if result.get('error'):
                            st.error(f"Error: {result['error']}")
                        else:
                            # Show retrievals
                            with st.expander("📚 Retrieved Context", expanded=False):
                                for i, ret in enumerate(result['retrievals'], 1):
                                    st.markdown(f"**Retrieval {i}** (Similarity: {1 - ret.get('distance', 0):.2%})")
                                    st.json(ret.get('metadata', {}))
                                    st.text(ret.get('document', '')[:500])
                                    st.divider()
                            
                            # Show answer
                            st.markdown("### 💡 Answer")
                            st.markdown(result['answer'])
                            
                            st.success("✓ Answer generated")
    
    with tab2:
        st.header("Vector Database Statistics")
        
        if sme.vector_db:
            stats = sme.get_vector_db_stats()
            st.json(stats)
            
            # Show code files stats
            st.info("Code files are stored in vector database. Mappings are extracted on-demand when you ask questions.")
            
            if st.button("Show Code Files Stats"):
                with st.spinner("Loading stats..."):
                    stats = sme.get_vector_db_stats()
                    st.metric("Total Code Files", stats.get('total_code_files', 0))
                    st.metric("Total Code Chunks", stats.get('total_code_chunks', stats.get('total_code_files', 0)))
                    if stats.get('legacy_mappings', 0) > 0:
                        st.info(f"Note: {stats.get('legacy_mappings', 0)} legacy mappings found (from old ingestion)")
                    
                    # Sample code files
                    if hasattr(sme.vector_db, 'code_collection'):
                        try:
                            sample = sme.vector_db.code_collection.get(limit=10)
                            if sample.get('ids'):
                                st.subheader("Sample Code Files")
                                for i, (file_id, metadata) in enumerate(zip(sample['ids'], sample['metadatas']), 1):
                                    with st.expander(f"File {i}: {metadata.get('file_name', 'N/A')}"):
                                        st.json(metadata)
                                        if sample.get('documents'):
                                            st.code(sample['documents'][i][:500] if i < len(sample['documents']) else '')
                        except Exception as e:
                            st.error(f"Error loading sample: {e}")
        else:
            st.warning("Vector database not enabled")
    
    with tab3:
        st.header("Search Code Files")
        
        search_query = st.text_input("Search Query", placeholder="e.g., OrderLine mapper or noteType mapping")
        n_results = st.number_input("Number of Results", min_value=1, max_value=20, value=5)
        
        if st.button("🔍 Search"):
            if not search_query:
                st.warning("Please enter a search query")
            else:
                with st.spinner("Searching..."):
                    results = sme.search_similar_code(search_query, n_results)
                    
                    if results:
                        st.success(f"Found {len(results)} similar code file(s)")
                        
                        for i, result in enumerate(results, 1):
                            metadata = result.get('metadata', {})
                            code = result.get('code', '') or result.get('document', '')
                            with st.expander(f"Result {i} (Similarity: {1 - result.get('distance', 0):.2%}) - {metadata.get('file_name', 'N/A')}"):
                                st.json(metadata)
                                st.markdown("**Code:**")
                                st.code(code[:1000] if len(code) > 1000 else code, language='java')
                    else:
                        st.info("No similar code files found")


if __name__ == "__main__":
    main()

