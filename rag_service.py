"""
RAG (Retrieval-Augmented Generation) Service
Combines vector database retrieval with LLM generation
"""
from typing import List, Dict, Optional
import json


class RAGService:
    """Service for RAG-based code understanding"""
    
    def __init__(self, ollama_client, vector_db, llm_model: str = "qwen2.5-coder:7b", 
                 extract_mappings_on_demand: bool = True):
        self.ollama_client = ollama_client
        self.vector_db = vector_db
        self.llm_model = llm_model
        self.extract_mappings_on_demand = extract_mappings_on_demand
        
        # Lazy import to avoid circular dependencies
        self._mapping_extractor = None
    
    def _get_mapping_extractor(self):
        """Get or create the on-demand mapping extractor"""
        if self._mapping_extractor is None:
            from mapping_extractor_on_demand import OnDemandMappingExtractor
            self._mapping_extractor = OnDemandMappingExtractor(
                ollama_client=self.ollama_client,
                use_llm=False  # Use parser by default (faster)
            )
        return self._mapping_extractor
    
    def build_context_from_retrievals(self, retrievals: List[Dict], code_retrievals: List[Dict] = None,
                                     extract_mappings: bool = None) -> str:
        """Build a context string from retrieved mappings and full code files
        
        Args:
            retrievals: Pre-extracted mappings (if available)
            code_retrievals: Retrieved code chunks
            extract_mappings: Whether to extract mappings from code on-demand (defaults to self.extract_mappings_on_demand)
        """
        context_parts = []
        extract_mappings = extract_mappings if extract_mappings is not None else self.extract_mappings_on_demand
        
        # Add full code files first (most important for LLM understanding)
        extracted_mappings = []
        if code_retrievals:
            context_parts.append("=== Relevant Code Files (Full Source Code) ===\n")
            for i, retrieval in enumerate(code_retrievals, 1):
                metadata = retrieval.get('metadata', {})
                code = retrieval.get('code', '') or retrieval.get('document', '')
                distance = retrieval.get('distance', 0)
                similarity = 1 - distance if distance else 0
                
                context_parts.append(f"\n--- Code File {i} (Similarity: {similarity:.2%}) ---")
                context_parts.append(f"File: {metadata.get('file_path', 'N/A')}")
                if metadata.get('chunk_index') is not None:
                    context_parts.append(f"Chunk: {metadata.get('chunk_index') + 1}/{metadata.get('total_chunks', '?')}")
                context_parts.append(f"\nFull Code:\n{code}")
                context_parts.append("")
                
                # Extract mappings on-demand if requested
                if extract_mappings and code:
                    extractor = self._get_mapping_extractor()
                    mappings = extractor.extract_from_code(code, metadata.get('file_path'))
                    if mappings.get('mappings'):
                        extracted_mappings.extend(mappings['mappings'])
        
        # Add extracted mappings (on-demand)
        if extracted_mappings:
            context_parts.append("=== Extracted Mappings (On-Demand) ===\n")
            for i, mapping in enumerate(extracted_mappings, 1):
                context_parts.append(f"\n--- Mapping {i} ---")
                context_parts.append(f"Type: {mapping.get('type', 'N/A')}")
                context_parts.append(f"Source: {mapping.get('source_type', 'N/A')} -> Target: {mapping.get('target_type', 'N/A')}")
                if mapping.get('method'):
                    context_parts.append(f"Method: {mapping.get('method')}")
                if mapping.get('field_mappings'):
                    context_parts.append("Field Mappings:")
                    for fm in mapping['field_mappings']:
                        context_parts.append(f"  {fm.get('source_field')} -> {fm.get('target_field')}")
                context_parts.append("")
        
        # Add pre-extracted mapping summaries (if available)
        if retrievals:
            context_parts.append("=== Pre-Extracted Mappings (Summary) ===\n")
            for i, retrieval in enumerate(retrievals, 1):
                metadata = retrieval.get('metadata', {})
                document = retrieval.get('document', '')
                distance = retrieval.get('distance', 0)
                similarity = 1 - distance if distance else 0
                
                context_parts.append(f"\n--- Mapping {i} (Similarity: {similarity:.2%}) ---")
                context_parts.append(f"File: {metadata.get('file_path', 'N/A')}")
                context_parts.append(f"Type: {metadata.get('mapping_type', 'N/A')}")
                context_parts.append(f"Source: {metadata.get('source_type', 'N/A')} -> Target: {metadata.get('target_type', 'N/A')}")
                if metadata.get('interface'):
                    context_parts.append(f"Interface: {metadata.get('interface')}")
                if metadata.get('method'):
                    context_parts.append(f"Method: {metadata.get('method')}")
                context_parts.append(f"\nDetails:\n{document}")
                context_parts.append("")
        
        if not context_parts:
            return "No relevant code or mappings found."
        
        return "\n".join(context_parts)
    
    def create_rag_prompt(self, question: str, context: str) -> str:
        """Create a RAG prompt for the LLM with full code context"""
        system_prompt = """You are an expert Java code understanding assistant specializing in MapStruct and POJO mappings. 
Your task is to analyze the provided FULL SOURCE CODE and answer questions with clear reasoning.

Guidelines:
1. Analyze the FULL CODE provided - you have the complete source code, not just summaries
2. Provide clear, detailed explanations based on the actual code
3. Reference specific lines, methods, and classes from the code
4. Explain the mapping logic and field transformations in detail
5. Identify where and how fields are used throughout the codebase
6. Be specific about source-to-destination mappings
7. If the code shows multiple related files, explain how they work together
8. If information is not available in the context, say so clearly"""
        
        prompt = f"""Based on the following FULL SOURCE CODE, answer this question: {question}

{context}

Please provide:
1. A detailed explanation based on the actual code provided
2. Specific references to classes, methods, and fields in the code
3. How the mapping logic works in the context of the full codebase
4. Where and how the fields are used throughout the code
5. Any important patterns or relationships you notice in the code

Answer:"""
        
        return prompt, system_prompt
    
    def answer_question(self, question: str, n_retrievals: int = 5, use_full_code: bool = True) -> Dict:
        """Answer a question using RAG with full code context"""
        result = {
            'question': question,
            'retrievals': [],
            'code_retrievals': [],
            'context': '',
            'answer': '',
            'error': None
        }
        
        try:
            # Step 1: Get embedding for the question
            question_embedding = self.ollama_client.get_embeddings(question)
            if not question_embedding:
                result['error'] = "Could not generate embedding for question"
                return result
            
            # Step 2: Retrieve similar mappings from vector DB
            mapping_retrievals = self.vector_db.search_similar(
                question_embedding, 
                n_results=n_retrievals
            )
            result['retrievals'] = mapping_retrievals
            
            # Step 3: Retrieve full code files if enabled
            code_retrievals = []
            if use_full_code and hasattr(self.vector_db, 'code_collection'):
                code_retrievals = self.vector_db.search_code(
                    question_embedding,
                    n_results=n_retrievals
                )
                result['code_retrievals'] = code_retrievals
            
            # Step 4: Build context from both mappings and full code
            context = self.build_context_from_retrievals(mapping_retrievals, code_retrievals)
            result['context'] = context
            
            # Step 4: Create RAG prompt
            prompt, system_prompt = self.create_rag_prompt(question, context)
            
            # Step 5: Generate answer using LLM
            answer = self.ollama_client.generate_with_llm(
                prompt=prompt,
                model=self.llm_model,
                system=system_prompt
            )
            
            if answer:
                result['answer'] = answer
            else:
                result['error'] = "Could not generate answer from LLM"
            
        except Exception as e:
            result['error'] = f"Error in RAG pipeline: {str(e)}"
        
        return result
    
    def answer_question_streaming(self, question: str, n_retrievals: int = 5, use_full_code: bool = True):
        """Answer a question using RAG with streaming response"""
        try:
            # Step 1: Get embedding for the question
            question_embedding = self.ollama_client.get_embeddings(question)
            if not question_embedding:
                yield {"error": "Could not generate embedding for question"}
                return
            
            # Step 2: Retrieve similar mappings from vector DB
            mapping_retrievals = self.vector_db.search_similar(
                question_embedding, 
                n_results=n_retrievals
            )
            
            # Step 3: Retrieve full code files if enabled
            code_retrievals = []
            if use_full_code and hasattr(self.vector_db, 'code_collection'):
                code_retrievals = self.vector_db.search_code(
                    question_embedding,
                    n_results=n_retrievals
                )
            
            # Step 4: Build context from both mappings and full code
            context = self.build_context_from_retrievals(mapping_retrievals, code_retrievals)
            
            # Step 4: Create RAG prompt
            prompt, system_prompt = self.create_rag_prompt(question, context)
            
            # Step 5: Generate answer using LLM with streaming
            response = self.ollama_client.generate_with_llm(
                prompt=prompt,
                model=self.llm_model,
                system=system_prompt,
                stream=True
            )
            
            if response:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if 'response' in data:
                                yield {"chunk": data['response'], "done": data.get('done', False)}
                            elif 'message' in data and 'content' in data['message']:
                                # Alternative format
                                yield {"chunk": data['message']['content'], "done": data.get('done', False)}
                        except json.JSONDecodeError:
                            # Try to decode as text if JSON fails
                            try:
                                decoded = line.decode('utf-8')
                                if decoded.strip():
                                    yield {"chunk": decoded, "done": False}
                            except:
                                continue
            else:
                yield {"error": "Could not generate answer from LLM"}
                
        except Exception as e:
            yield {"error": f"Error in RAG pipeline: {str(e)}"}

