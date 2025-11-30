"""
Vector Database for storing and querying code mapping embeddings
"""
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("Warning: chromadb not installed. Vector database features will be disabled.")


class VectorDatabase:
    """Vector database for storing and querying code mapping embeddings"""
    
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "code_mappings", 
                 code_collection_name: str = "code_files"):
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb is not installed. Install it with: pip install chromadb")
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection for mappings
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Code mapping embeddings"}
        )
        
        # Get or create collection for full code files
        self.code_collection = self.client.get_or_create_collection(
            name=code_collection_name,
            metadata={"description": "Full code file embeddings"}
        )
    
    def _generate_id(self, mapping: Dict, file_path: str) -> str:
        """Generate a unique ID for a mapping"""
        # Create a hash from mapping details including field mappings for uniqueness
        field_mappings = mapping.get('field_mappings', [])
        # Create a unique string from field mappings
        fields_str = json.dumps(field_mappings, sort_keys=True) if field_mappings else ''
        
        mapping_str = json.dumps({
            'file': file_path,
            'type': mapping.get('type'),
            'source_type': mapping.get('source_type'),
            'target_type': mapping.get('target_type'),
            'method': mapping.get('method', ''),
            'interface': mapping.get('interface', ''),
            'source_field': mapping.get('source_field', ''),
            'target_field': mapping.get('target_field', ''),
            'fields': fields_str,
        }, sort_keys=True)
        return hashlib.md5(mapping_str.encode()).hexdigest()
    
    def _create_document(self, mapping: Dict, file_path: str, code_snippet: str = "") -> str:
        """Create a document string from mapping for embedding"""
        parts = []
        
        parts.append(f"Mapping Type: {mapping.get('type', 'unknown')}")
        parts.append(f"Source Type: {mapping.get('source_type', 'N/A')}")
        parts.append(f"Target Type: {mapping.get('target_type', 'N/A')}")
        
        if mapping.get('interface'):
            parts.append(f"Interface: {mapping['interface']}")
        if mapping.get('method'):
            parts.append(f"Method: {mapping['method']}")
        
        if mapping.get('field_mappings'):
            parts.append("Field Mappings:")
            for fm in mapping['field_mappings']:
                source = fm.get('source', 'N/A')
                target = fm.get('target', 'N/A')
                parts.append(f"  {source} -> {target}")
                if fm.get('expression'):
                    parts.append(f"    Expression: {fm['expression']}")
        
        if code_snippet:
            parts.append(f"\nCode:\n{code_snippet[:500]}")  # Limit code snippet size
        
        return "\n".join(parts)
    
    def store_mapping(self, mapping: Dict, file_path: str, embedding: List[float], 
                     code_snippet: str = "", metadata: Optional[Dict] = None) -> str:
        """Store a mapping with its embedding in the vector database"""
        mapping_id = self._generate_id(mapping, file_path)
        document = self._create_document(mapping, file_path, code_snippet)
        
        # Prepare metadata
        db_metadata = {
            'file_path': file_path,
            'mapping_type': mapping.get('type', 'unknown'),
            'source_type': mapping.get('source_type', ''),
            'target_type': mapping.get('target_type', ''),
            'interface': mapping.get('interface', ''),
            'method': mapping.get('method', ''),
        }
        
        if metadata:
            db_metadata.update(metadata)
        
        # Store in ChromaDB
        self.collection.add(
            ids=[mapping_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[db_metadata]
        )
        
        return mapping_id
    
    def store_mappings_batch(self, mappings: List[Dict], file_path: str, 
                            embeddings: List[List[float]], code_snippet: str = "") -> List[str]:
        """Store multiple mappings in batch"""
        ids = []
        documents = []
        metadatas = []
        
        # Track IDs to avoid duplicates within the batch
        seen_ids = set()
        
        for mapping, embedding in zip(mappings, embeddings):
            mapping_id = self._generate_id(mapping, file_path)
            
            # If duplicate ID, add a counter to make it unique
            original_id = mapping_id
            counter = 0
            while mapping_id in seen_ids:
                counter += 1
                mapping_id = f"{original_id}_{counter}"
            
            seen_ids.add(mapping_id)
            
            document = self._create_document(mapping, file_path, code_snippet)
            
            metadata = {
                'file_path': file_path,
                'mapping_type': mapping.get('type', 'unknown'),
                'source_type': mapping.get('source_type', ''),
                'target_type': mapping.get('target_type', ''),
                'interface': mapping.get('interface', ''),
                'method': mapping.get('method', ''),
            }
            
            ids.append(mapping_id)
            documents.append(document)
            metadatas.append(metadata)
        
        # Check for existing IDs and remove duplicates
        if ids:
            try:
                existing = self.collection.get(ids=ids)
                existing_ids = set(existing.get('ids', []))
                # Filter out existing IDs
                filtered_data = []
                for i, mapping_id in enumerate(ids):
                    if mapping_id not in existing_ids:
                        filtered_data.append((mapping_id, documents[i], metadatas[i], embeddings[i]))
                
                if filtered_data:
                    filtered_ids, filtered_docs, filtered_metas, filtered_embs = zip(*filtered_data)
                    # Store in batch
                    self.collection.add(
                        ids=list(filtered_ids),
                        embeddings=list(filtered_embs),
                        documents=list(filtered_docs),
                        metadatas=list(filtered_metas)
                    )
                else:
                    print(f"  ℹ All {len(ids)} mappings already exist in database")
            except Exception as e:
                # If get fails (maybe collection is empty), try direct add
                try:
                    self.collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas
                    )
                except Exception as e2:
                    # If still getting duplicates, try adding one by one
                    if "duplicate" in str(e2).lower() or "unique" in str(e2).lower():
                        print(f"  ⚠ Batch insert failed due to duplicates, inserting individually...")
                        stored = 0
                        for i, (mapping_id, doc, meta, emb) in enumerate(zip(ids, documents, metadatas, embeddings)):
                            try:
                                # Check if exists first
                                try:
                                    existing = self.collection.get(ids=[mapping_id])
                                    if existing.get('ids'):
                                        continue  # Skip if exists
                                except:
                                    pass  # If get fails, try to add
                                
                                self.collection.add(
                                    ids=[mapping_id],
                                    embeddings=[emb],
                                    documents=[doc],
                                    metadatas=[meta]
                                )
                                stored += 1
                            except Exception as e3:
                                if "duplicate" not in str(e3).lower():
                                    print(f"  ✗ Failed to store mapping {i+1}: {e3}")
                        if stored > 0:
                            print(f"  ✓ Stored {stored} new mapping(s) (skipped duplicates)")
                    else:
                        raise
        
        return ids
    
    def search_similar(self, query_embedding: List[float], n_results: int = 5, 
                     filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """Search for similar mappings using embedding similarity"""
        query_kwargs = {
            'query_embeddings': [query_embedding],
            'n_results': n_results
        }
        
        if filter_metadata:
            query_kwargs['where'] = filter_metadata
        
        results = self.collection.query(**query_kwargs)
        
        # Format results
        similar_mappings = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                similar_mappings.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return similar_mappings
    
    def search_by_text(self, query_text: str, n_results: int = 5, 
                      filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """Search for mappings by text query (will need embedding first)"""
        # Note: ChromaDB can do text search if you provide query_texts instead of query_embeddings
        # But for better results with custom embeddings, we'd need to embed the text first
        query_kwargs = {
            'query_texts': [query_text],
            'n_results': n_results
        }
        
        if filter_metadata:
            query_kwargs['where'] = filter_metadata
        
        results = self.collection.query(**query_kwargs)
        
        # Format results
        similar_mappings = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                similar_mappings.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return similar_mappings
    
    def get_all_mappings(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all stored mappings"""
        results = self.collection.get(limit=limit)
        
        mappings = []
        if results['ids']:
            for i in range(len(results['ids'])):
                mappings.append({
                    'id': results['ids'][i],
                    'document': results['documents'][i],
                    'metadata': results['metadatas'][i]
                })
        
        return mappings
    
    def delete_mapping(self, mapping_id: str):
        """Delete a mapping by ID"""
        self.collection.delete(ids=[mapping_id])
    
    def delete_by_file(self, file_path: str):
        """Delete all mappings from a specific file"""
        # Get all mappings from this file
        results = self.collection.get(
            where={'file_path': file_path}
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector database"""
        code_count = self.code_collection.count()
        mapping_count = self.collection.count()  # Legacy - may have old mappings
        
        return {
            'total_code_files': code_count,
            'total_code_chunks': code_count,  # Alias for clarity
            'legacy_mappings': mapping_count,  # Old mappings if any
            'code_collection': self.code_collection.name,
            'mapping_collection': self.collection.name
        }
    
    def clear(self, clear_code_files: bool = True):
        """Clear all mappings and optionally code files from the database"""
        self.client.delete_collection(name=self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"description": "Code mapping embeddings"}
        )
        
        if clear_code_files:
            self.client.delete_collection(name=self.code_collection.name)
            self.code_collection = self.client.get_or_create_collection(
                name=self.code_collection.name,
                metadata={"description": "Full code file embeddings"}
            )
    
    def store_code_file(self, file_path: str, code_content: str, embedding: List[float], 
                       metadata: Optional[Dict] = None) -> str:
        """Store a full code file with its embedding"""
        # Generate ID from file path
        file_id = hashlib.md5(file_path.encode()).hexdigest()
        
        # Prepare metadata
        db_metadata = {
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'file_type': Path(file_path).suffix,
        }
        
        if metadata:
            db_metadata.update(metadata)
        
        # Store in ChromaDB
        self.code_collection.add(
            ids=[file_id],
            embeddings=[embedding],
            documents=[code_content],
            metadatas=[db_metadata]
        )
        
        return file_id
    
    def store_code_file_chunked(self, file_path: str, code_content: str, embeddings: List[List[float]],
                                chunk_size: int = 2000, chunk_indices: Optional[List[int]] = None) -> List[str]:
        """Store a large code file in chunks
        
        Args:
            file_path: Path to the code file
            code_content: Full content of the file
            embeddings: List of embeddings (only for successfully embedded chunks)
            chunk_size: Size of each chunk in characters
            chunk_indices: Optional list of chunk indices that correspond to embeddings
                          If None, assumes embeddings are in order starting from chunk 0
        """
        if not embeddings:
            return []
        
        # Split into chunks
        chunks = []
        chunk_embeddings = []
        chunk_ids = []
        
        total_chunks = (len(code_content) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(code_content), chunk_size):
            chunk = code_content[i:i + chunk_size]
            chunks.append(chunk)
        
        # Map embeddings to chunks
        if chunk_indices:
            # Use provided indices to map embeddings to chunks
            for idx, emb in zip(chunk_indices, embeddings):
                if 0 <= idx < len(chunks):
                    chunk_embeddings.append((idx, emb))
        else:
            # Assume embeddings are in order
            for i, emb in enumerate(embeddings):
                if i < len(chunks):
                    chunk_embeddings.append((i, emb))
        
        # Store only chunks that have embeddings
        stored_ids = []
        for chunk_idx, emb in chunk_embeddings:
            chunk = chunks[chunk_idx]
            chunk_id = f"{hashlib.md5(file_path.encode()).hexdigest()}_chunk_{chunk_idx}"
            metadata = {
                'file_path': file_path,
                'file_name': Path(file_path).name,
                'file_type': Path(file_path).suffix,
                'chunk_index': chunk_idx,
                'total_chunks': total_chunks
            }
            
            try:
                self.code_collection.add(
                    ids=[chunk_id],
                    embeddings=[emb],
                    documents=[chunk],
                    metadatas=[metadata]
                )
                stored_ids.append(chunk_id)
            except Exception as e:
                # Skip duplicate or other errors
                if "duplicate" not in str(e).lower():
                    print(f"  ⚠ Failed to store chunk {chunk_idx + 1}: {e}")
        
        return stored_ids
    
    def search_code(self, query_embedding: List[float], n_results: int = 5,
                   filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """Search for similar code files using embedding similarity"""
        query_kwargs = {
            'query_embeddings': [query_embedding],
            'n_results': n_results
        }
        
        if filter_metadata:
            query_kwargs['where'] = filter_metadata
        
        results = self.code_collection.query(**query_kwargs)
        
        # Format results
        similar_code = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                similar_code.append({
                    'id': results['ids'][0][i],
                    'code': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return similar_code
    
    def get_code_stats(self) -> Dict:
        """Get statistics about the code collection"""
        count = self.code_collection.count()
        return {
            'total_files': count,
            'collection_name': self.code_collection.name
        }

