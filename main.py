#!/usr/bin/env python3
"""
AI Team Member - Code Understanding SME
Extracts source to destination field-level mappings from Java code
"""
import argparse
import sys
import yaml
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from java_parser import JavaParser
from mapping_extractor import MappingExtractor
from ollama_client import OllamaClient
from vector_db import VectorDatabase, CHROMADB_AVAILABLE


class CodeUnderstandingSME:
    """AI Team Member specialized in code understanding and mapping extraction"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.parser = JavaParser()
        self.extractor = MappingExtractor(self.parser)
        self.ollama_client = None
        self.vector_db = None
        
        if self.config.get('embeddings', {}).get('enabled', True):
            max_concurrent = self.config.get('input', {}).get('max_concurrent_embedding_requests', 2)
            self.ollama_client = OllamaClient(
                base_url=self.config['embeddings']['base_url'],
                model=self.config['embeddings']['model'],
                max_concurrent_requests=max_concurrent
            )
        
        # Initialize vector database if enabled
        if self.config.get('vector_db', {}).get('enabled', False):
            if CHROMADB_AVAILABLE:
                try:
                    code_collection_name = self.config.get('vector_db', {}).get('code_collection_name', 'code_files')
                    self.vector_db = VectorDatabase(
                        persist_directory=self.config['vector_db']['persist_directory'],
                        collection_name=self.config['vector_db']['collection_name'],
                        code_collection_name=code_collection_name
                    )
                    print(f"✓ Vector database initialized at {self.config['vector_db']['persist_directory']}")
                except Exception as e:
                    print(f"Warning: Could not initialize vector database: {e}")
            else:
                print("Warning: chromadb not installed. Vector database features disabled.")
                print("Install with: pip install chromadb")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            print("Using default configuration")
            return self._default_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._default_config()
    
    def _default_config(self) -> dict:
        """Return default configuration"""
        return {
            'input': {
                'projects': [],
                'codebase_path': '',
                'file_extensions': ['.java'],
                'recursive': True,
                'auto_process': False,
                'exclude_patterns': [
                    '**/src/test/**',
                    '**/target/**',
                    '**/build/**',
                    '**/node_modules/**',
                    '**/.git/**',
                    '**/src/main/resources/**'
                ],
                'embedding_batch_size': 50,
                'parallel_workers': 4,
                'embedding_parallel_workers': 4,
                'file_chunk_size': 1000,
                'enable_checkpoint': True,
                'checkpoint_interval': 500
            },
            'mapping': {
                'types': ['mapstruct', 'pojo']
            },
            'embeddings': {
                'enabled': True,
                'model': 'unclemusclez/jina-embeddings-v2-base-code',
                'base_url': 'http://localhost:11434'
            },
            'vector_db': {
                'enabled': True,
                'persist_directory': './chroma_db',
                'collection_name': 'code_mappings',
                'store_on_process': True,
                'enable_similarity_search': True
            },
            'output': {
                'format': 'json',
                'output_path': '',
                'include_code_snippets': True
            }
        }
    
    def process_file(self, file_path: str, verbose: bool = False) -> dict:
        """Process a single Java file - stores full code, extracts mappings on-demand"""
        if verbose:
            print(f"Processing file: {file_path}")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code_content = f.read()
            
            # Store full code file in vector DB (this is the main goal - mappings extracted on-demand)
            if self.vector_db and self.config.get('vector_db', {}).get('store_full_code', True):
                if self.ollama_client and self.config.get('embeddings', {}).get('enabled'):
                    if self.ollama_client.check_connection():
                        self._store_full_code_file(file_path, code_content, verbose=verbose)
                    else:
                        if verbose:
                            print(f"  ⚠ Warning: Ollama not available. Code file not stored.")
                            print(f"     Run 'ollama pull {self.ollama_client.model}' to install the model.")
                else:
                    if verbose:
                        print(f"  ⚠ Warning: Embeddings disabled. Code file not stored.")
            
            # Return file info - mappings will be extracted on-demand from retrieved code
            if verbose:
                print(f"  ✓ Stored code file (mappings will be extracted on-demand)")
            return {
                'file': file_path,
                'status': 'stored',
                'summary': {
                    'code_stored': True
                }
            }
        except Exception as e:
            if verbose:
                print(f"Error processing file {file_path}: {e}")
            import traceback
            if verbose:
                traceback.print_exc()
            return {'error': str(e), 'file': file_path}
    
    def process_directory(self, directory_path: str) -> list:
        """Process all Java files in a directory with exclusions (optimized for large codebases)"""
        recursive = self.config.get('input', {}).get('recursive', True)
        extensions = self.config.get('input', {}).get('file_extensions', ['.java'])
        exclude_patterns = self.config.get('input', {}).get('exclude_patterns', [])
        parallel_workers = self.config.get('input', {}).get('parallel_workers', 4)
        file_chunk_size = self.config.get('input', {}).get('file_chunk_size', 1000)
        enable_checkpoint = self.config.get('input', {}).get('enable_checkpoint', True)
        checkpoint_interval = self.config.get('input', {}).get('checkpoint_interval', 500)
        
        print(f"Discovering Java files in {directory_path}...")
        java_files = self.parser.find_java_files(
            directory_path, 
            recursive, 
            extensions,
            exclude_patterns
        )
        
        total_files = len(java_files)
        print(f"Found {total_files:,} Java file(s) (after exclusions)")
        
        if total_files == 0:
            return []
        
        # For very large codebases (30k+ files), process in chunks
        if total_files > 10000:
            print(f"Large codebase detected. Processing in chunks of {file_chunk_size:,} files...")
            return self._process_files_chunked(
                java_files, 
                parallel_workers, 
                file_chunk_size,
                enable_checkpoint,
                checkpoint_interval
            )
        # Use parallel processing for medium codebases
        elif total_files > 100 and parallel_workers > 1:
            return self._process_files_parallel(java_files, parallel_workers)
        else:
            # Sequential processing for smaller codebases
            results = []
            verbose = self.config.get('input', {}).get('verbose', False)
            for file_path in tqdm(java_files, desc="Processing files", unit="file"):
                result = self.process_file(file_path, verbose=verbose)
                results.append(result)
            return results
    
    def _process_files_parallel(self, java_files: List[str], max_workers: int) -> list:
        """Process files in parallel for better performance"""
        results = []
        
        # Limit max_workers to prevent too many concurrent file operations
        # Each file may spawn multiple embedding requests, so we need to balance
        effective_workers = min(max_workers, 4)  # Cap at 4 to prevent overwhelming system
        
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self.process_file, file_path): file_path 
                for file_path in java_files
            }
            
            # Process completed tasks with progress bar
            for future in tqdm(as_completed(future_to_file), total=len(java_files), desc="Processing files", unit="file"):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    file_path = future_to_file[future]
                    print(f"Error processing {file_path}: {e}")
                    results.append({'error': str(e), 'file': file_path})
        
        return results
    
    def _process_files_chunked(self, java_files: List[str], max_workers: int, 
                               chunk_size: int, enable_checkpoint: bool, 
                               checkpoint_interval: int) -> list:
        """Process files in chunks for very large codebases (30k+ files)"""
        total_files = len(java_files)
        total_chunks = (total_files + chunk_size - 1) // chunk_size
        results = []
        processed_count = 0
        
        print(f"Processing {total_files:,} files in {total_chunks} chunks of ~{chunk_size:,} files each")
        
        for chunk_idx in range(total_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_files)
            chunk_files = java_files[start_idx:end_idx]
            
            print(f"\nChunk {chunk_idx + 1}/{total_chunks}: Processing files {start_idx + 1:,} to {end_idx:,}")
            
            # Process chunk in parallel
            if len(chunk_files) > 100 and max_workers > 1:
                chunk_results = self._process_files_parallel(chunk_files, max_workers)
            else:
                chunk_results = []
                for file_path in tqdm(chunk_files, desc=f"Chunk {chunk_idx + 1}", unit="file", leave=False):
                    result = self.process_file(file_path, verbose=False)
                    chunk_results.append(result)
            
            results.extend(chunk_results)
            processed_count += len(chunk_results)
            
            # Progress update
            progress_pct = (processed_count / total_files) * 100
            print(f"Progress: {processed_count:,}/{total_files:,} files ({progress_pct:.1f}%)")
            
            # Optional checkpoint (save progress)
            if enable_checkpoint and processed_count % checkpoint_interval == 0:
                print(f"  ✓ Checkpoint: {processed_count:,} files processed")
                # Note: Vector DB already persists, so this is mainly for logging
        
        return results
    
    def process_configured_codebase(self) -> list:
        """Process the codebase(s) configured in config.yaml (supports multiple projects)"""
        projects = self.config.get('input', {}).get('projects', [])
        codebase_path = self.config.get('input', {}).get('codebase_path', '')
        
        # Use projects list if available, otherwise fall back to codebase_path
        if not projects and codebase_path:
            projects = [codebase_path]
        
        if not projects:
            print("No projects or codebase_path configured in config.yaml")
            return []
        
        # Limit to 10 projects
        if len(projects) > 10:
            print(f"Warning: More than 10 projects specified. Processing first 10.")
            projects = projects[:10]
        
        all_results = []
        
        # Process projects in parallel if multiple projects
        if len(projects) > 1:
            # Limit to 2 projects in parallel to avoid overwhelming Ollama
            # Each project processes files in parallel, so we don't want too many projects at once
            parallel_workers = min(len(projects), 2)
            
            def process_project(project_info):
                i, project_path = project_info
                project_path = project_path.strip()
                if not project_path:
                    return []
                
                project_path_obj = Path(project_path)
                
                if not project_path_obj.exists():
                    print(f"Warning: Project path does not exist: {project_path}")
                    return []
                
                print(f"\n[{i}/{len(projects)}] Processing project: {project_path}")
                
                if project_path_obj.is_file():
                    result = self.process_file(str(project_path_obj))
                    return [result]
                elif project_path_obj.is_dir():
                    results = self.process_directory(str(project_path_obj))
                    return results
                else:
                    print(f"Error: Invalid project path: {project_path}")
                    return []
            
            # Process projects in parallel (limited to 2 at a time)
            with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                project_tasks = [(i+1, proj) for i, proj in enumerate(projects)]
                project_results = list(executor.map(process_project, project_tasks))
                
                # Flatten results
                for results in project_results:
                    all_results.extend(results)
        else:
            # Single project - process sequentially (simpler)
            for i, project_path in enumerate(projects, 1):
                project_path = project_path.strip()
                if not project_path:
                    continue
                
                project_path_obj = Path(project_path)
                
                if not project_path_obj.exists():
                    print(f"Warning: Project path does not exist: {project_path}")
                    continue
                
                print(f"\n[{i}/{len(projects)}] Processing project: {project_path}")
                
                if project_path_obj.is_file():
                    result = self.process_file(str(project_path_obj))
                    all_results.append(result)
                elif project_path_obj.is_dir():
                    results = self.process_directory(str(project_path_obj))
                    all_results.extend(results)
                else:
                    print(f"Error: Invalid project path: {project_path}")
        
        return all_results
    
    def process_content(self, content: str, file_path: str = "inline") -> dict:
        """Process Java code content directly"""
        print(f"Processing inline code content")
        
        try:
            # Store full code file in vector DB (mappings extracted on-demand)
            if self.vector_db and self.config.get('vector_db', {}).get('store_full_code', True):
                if self.ollama_client and self.config.get('embeddings', {}).get('enabled'):
                    if self.ollama_client.check_connection():
                        self._store_full_code_file(file_path, content, verbose=False)
                    else:
                        print(f"Warning: Ollama not available. Run 'ollama pull {self.ollama_client.model}' to install the model.")
            
            return {
                'file': file_path,
                'status': 'stored',
                'summary': {
                    'code_stored': True
                }
            }
        except Exception as e:
            print(f"Error processing content: {e}")
            return {'error': str(e), 'file': file_path}
    
    def output_results(self, results: dict or list, output_path: Optional[str] = None):
        """Output results in the specified format"""
        output_format = self.config.get('output', {}).get('format', 'json')
        output_file = output_path or self.config.get('output', {}).get('output_path', '')
        
        if isinstance(results, list):
            # Multiple files processed
            stored_count = sum(1 for r in results if r.get('summary', {}).get('code_stored', False))
            combined = {
                'files_processed': len(results),
                'files_stored': stored_count,
                'results': results,
                'summary': {
                    'code_files_stored': stored_count
                }
            }
            if output_format == 'json':
                import json
                formatted = json.dumps(combined, indent=2)
            elif output_format == 'yaml':
                import yaml
                formatted = yaml.dump(combined, default_flow_style=False)
            else:
                formatted = self.format_results(results)
        else:
            # Single result
            if output_format == 'json':
                import json
                formatted = json.dumps(results, indent=2)
            elif output_format == 'yaml':
                import yaml
                formatted = yaml.dump(results, default_flow_style=False)
            else:
                formatted = f"File: {results.get('file', 'N/A')}, Status: {results.get('status', 'N/A')}"
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(formatted)
            print(f"Results written to: {output_file}")
        else:
            print("\n" + "="*80)
            print("MAPPING EXTRACTION RESULTS")
            print("="*80 + "\n")
            print(formatted)
    
    def _format_multiple_text(self, results: list) -> str:
        """Format multiple results as text"""
        lines = []
        lines.append(f"Processed {len(results)} file(s)\n")
        
        for result in results:
            lines.append(self.extractor.format_mappings(result, 'text'))
            lines.append("\n" + "-"*80 + "\n")
        
        return "\n".join(lines)
    
    def _store_full_code_file(self, file_path: str, code_content: str, verbose: bool = False):
        """Store full code file in vector database"""
        if not self.vector_db or not self.ollama_client:
            return
        
        try:
            max_chunk_size = self.config.get('vector_db', {}).get('max_code_chunk_size', 2000)
            
            # Use smaller chunks for embeddings to avoid EOF errors
            # Jina embeddings model has issues with large chunks, so use 2000 chars max
            embedding_chunk_size = min(max_chunk_size, 2000)  # Very small chunks to avoid EOF errors
            
            # For very large files, always chunk to avoid embedding errors
            if len(code_content) <= embedding_chunk_size:
                # Single embedding for entire file
                embedding = self.ollama_client.get_embeddings(code_content)
                if embedding:
                    self.vector_db.store_code_file(file_path, code_content, embedding)
                else:
                    if verbose:
                        print(f"  ⚠ Failed to generate embedding for {Path(file_path).name} (skipping)")
            else:
                # Split into chunks and embed each
                chunks = []
                embeddings = []
                chunk_indices = []
                
                total_chunks = (len(code_content) + embedding_chunk_size - 1) // embedding_chunk_size
                
                # Prepare all chunks first
                chunk_data = []
                for i in range(0, len(code_content), embedding_chunk_size):
                    chunk = code_content[i:i + embedding_chunk_size]
                    chunk_num = i // embedding_chunk_size + 1
                    chunk_data.append((chunk_num - 1, chunk, chunk_num, total_chunks))
                
                # Generate embeddings in parallel for better performance
                # Balance throughput with stability
                embedding_workers = min(
                    self.config.get('input', {}).get('embedding_parallel_workers', 3),
                    4  # Cap at 4 for reasonable throughput
                )
                
                # Slightly reduce for very large files (but not too much)
                if len(chunk_data) > 20:
                    embedding_workers = max(2, embedding_workers - 1)  # Keep at least 2 workers
                
                def embed_chunk(chunk_info):
                    chunk_idx, chunk, chunk_num, total = chunk_info
                    emb = self.ollama_client.get_embeddings(chunk)
                    return (chunk_idx, emb, chunk_num, total)
                
                # Use ThreadPoolExecutor for parallel embedding generation
                # Limited parallelism to prevent overwhelming Ollama
                # The semaphore in OllamaClient will further limit concurrent requests
                with ThreadPoolExecutor(max_workers=embedding_workers) as executor:
                    embedding_results = list(executor.map(embed_chunk, chunk_data))
                
                # Process results and store successful embeddings
                for chunk_idx, emb, chunk_num, total in embedding_results:
                    if emb:
                        embeddings.append(emb)
                        chunk_indices.append(chunk_idx)
                    else:
                        # Skip failed chunks but continue processing
                        if verbose:
                            print(f"  ⚠ Failed to generate embedding for chunk {chunk_num}/{total} of {Path(file_path).name} (skipping chunk)")
                
                if embeddings:
                    # Store only successfully embedded chunks
                    self.vector_db.store_code_file_chunked(file_path, code_content, embeddings, embedding_chunk_size, chunk_indices)
                    if verbose and len(embeddings) < len(chunks):
                        print(f"  ✓ Stored {len(embeddings)}/{len(chunks)} chunks for {Path(file_path).name}")
                else:
                    if verbose:
                        print(f"  ⚠ No embeddings generated for {Path(file_path).name} (all chunks failed)")
            
        except Exception as e:
            print(f"  ⚠ Could not store full code file {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
    def search_similar_code(self, query_text: str, n_results: int = 5) -> list:
        """Search for similar code files using vector database"""
        if not self.vector_db:
            print("Vector database is not enabled")
            return []
        
        if not self.ollama_client:
            print("Ollama client is not available")
            return []
        
        try:
            # Get embedding for query
            query_embedding = self.ollama_client.get_embeddings(query_text)
            if not query_embedding:
                print("Could not generate embedding for query")
                return []
            
            # Search in code collection
            results = self.vector_db.search_code(query_embedding, n_results)
            return results
        except Exception as e:
            print(f"Error searching similar code: {e}")
            return []
    
    def get_vector_db_stats(self) -> dict:
        """Get statistics about the vector database"""
        if not self.vector_db:
            return {'error': 'Vector database not enabled'}
        
        return self.vector_db.get_stats()


def main():
    parser = argparse.ArgumentParser(
        description='AI Code Understanding SME - Extract field-level mappings from Java code'
    )
    parser.add_argument(
        'input',
        nargs='?',
        help='Path to Java file or directory, or "-" to read from stdin. If not provided, uses codebase_path from config.yaml'
    )
    parser.add_argument(
        '--process-codebase',
        action='store_true',
        help='Process the codebase_path configured in config.yaml'
    )
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file path (overrides config)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'yaml', 'text'],
        help='Output format (overrides config)'
    )
    parser.add_argument(
        '--check-ollama',
        action='store_true',
        help='Check if Ollama is available and model is installed'
    )
    parser.add_argument(
        '--search',
        help='Search for similar code files (requires vector DB)'
    )
    parser.add_argument(
        '--db-stats',
        action='store_true',
        help='Show vector database statistics'
    )
    parser.add_argument(
        '--test-file',
        help='Test processing a single file with verbose output'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output during processing'
    )
    parser.add_argument(
        '--clear-db',
        action='store_true',
        help='Clear/reset the vector database (WARNING: This deletes all stored mappings)'
    )
    
    args = parser.parse_args()
    
    # Initialize the SME
    sme = CodeUnderstandingSME(args.config)
    
    # Override config with command line arguments
    if args.format:
        sme.config['output']['format'] = args.format
    if args.output:
        sme.config['output']['output_path'] = args.output
    
    # Check Ollama if requested
    if args.check_ollama:
        if sme.ollama_client:
            if sme.ollama_client.check_connection():
                print(f"✓ Ollama is running and model '{sme.ollama_client.model}' is available")
            else:
                print(f"✗ Ollama is not available or model '{sme.ollama_client.model}' is not installed")
                print(f"  Run: ollama pull {sme.ollama_client.model}")
        else:
            print("Embeddings are disabled in configuration")
        return
    
    # Show vector DB stats if requested
    if args.db_stats:
        stats = sme.get_vector_db_stats()
        import json
        print(json.dumps(stats, indent=2))
        return
    
    # Clear vector database if requested
    if args.clear_db:
        if sme.vector_db:
            print("WARNING: This will delete ALL mappings from the vector database!")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                sme.vector_db.clear()
                print("✓ Vector database cleared successfully")
            else:
                print("Operation cancelled")
        else:
            print("Vector database is not enabled")
        return
    
    # Test file processing if requested
    if args.test_file:
        print(f"Testing file processing: {args.test_file}")
        print("="*80)
        result = sme.process_file(args.test_file, verbose=True)
        print("\n" + "="*80)
        print("RESULT:")
        import json
        print(json.dumps(result, indent=2))
        return
    
    # Search for similar mappings if requested
    if args.search:
        results = sme.search_similar_code(args.search, n_results=5)
        if results:
            print(f"\nFound {len(results)} similar code file(s) for: '{args.search}'\n")
            for i, result in enumerate(results, 1):
                print(f"{i}. Similarity: {1 - result.get('distance', 0):.3f}")
                print(f"   File: {result['metadata'].get('file_path', 'N/A')}")
                if result['metadata'].get('chunk_index') is not None:
                    print(f"   Chunk: {result['metadata'].get('chunk_index') + 1}/{result['metadata'].get('total_chunks', '?')}")
                code = result.get('code', '') or result.get('document', '')
                print(f"   Code preview: {code[:200]}...")
                print()
        else:
            print("No similar code files found")
        return
    
    # Process configured codebase if requested
    if args.process_codebase:
        results = sme.process_configured_codebase()
        if not results:
            sys.exit(1)
        sme.output_results(results, args.output)
        return
    
    # Process input
    if not args.input:
        # Try to use configured codebase path
        codebase_path = sme.config.get('input', {}).get('codebase_path', '')
        if codebase_path:
            print(f"Using configured codebase path: {codebase_path}")
            results = sme.process_configured_codebase()
            if not results:
                sys.exit(1)
        else:
            print("Error: No input specified and no codebase_path in config.yaml")
            print("Usage: python main.py <file_or_directory> or python main.py - < <code>")
            print("Or configure 'codebase_path' in config.yaml")
            print("Or use: python main.py --process-codebase")
            sys.exit(1)
    elif args.input == '-':
        # Read from stdin
        content = sys.stdin.read()
        results = sme.process_content(content)
    else:
        input_path = Path(args.input)
        if input_path.is_file():
            results = sme.process_file(str(input_path))
        elif input_path.is_dir():
            results = sme.process_directory(str(input_path))
        else:
            print(f"Error: Path not found: {args.input}")
            sys.exit(1)
    
    # Output results
    sme.output_results(results, args.output)


if __name__ == '__main__':
    main()

