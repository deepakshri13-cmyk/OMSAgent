"""
On-demand mapping extraction from retrieved code
Can use parser or LLM to extract mappings from code chunks
"""
from typing import List, Dict, Optional
from java_parser import JavaParser
from mapping_extractor import MappingExtractor


class OnDemandMappingExtractor:
    """Extract mappings from retrieved code on-demand"""
    
    def __init__(self, ollama_client=None, use_llm: bool = False):
        self.parser = JavaParser()
        self.extractor = MappingExtractor(self.parser)
        self.ollama_client = ollama_client
        self.use_llm = use_llm and ollama_client is not None
    
    def extract_from_code(self, code_content: str, file_path: str = None, 
                         use_llm: Optional[bool] = None) -> Dict:
        """Extract mappings from code content
        
        Args:
            code_content: Full code content to extract mappings from
            file_path: Optional file path for context
            use_llm: Override default LLM usage (if None, uses self.use_llm)
        
        Returns:
            Dictionary with extracted mappings
        """
        use_llm = use_llm if use_llm is not None else self.use_llm
        
        if use_llm and self.ollama_client:
            return self._extract_with_llm(code_content, file_path)
        else:
            return self._extract_with_parser(code_content, file_path)
    
    def _extract_with_parser(self, code_content: str, file_path: str = None) -> Dict:
        """Extract mappings using the Java parser (fast, rule-based)"""
        try:
            # Use the extractor's method that works with content strings
            result = self.extractor.extract_mappings_from_content(code_content, file_path or '')
            
            # Normalize field_mappings format for consistency
            for mapping in result.get('mappings', []):
                if mapping.get('field_mappings'):
                    normalized_fields = []
                    for fm in mapping['field_mappings']:
                        # Handle both formats: source/target and source_field/target_field
                        normalized = {
                            'source_field': fm.get('source_field') or fm.get('source', ''),
                            'target_field': fm.get('target_field') or fm.get('target', ''),
                        }
                        if fm.get('expression'):
                            normalized['expression'] = fm['expression']
                        if fm.get('ignore'):
                            normalized['ignore'] = fm['ignore']
                        if fm.get('target_path'):
                            normalized['target_path'] = fm['target_path']
                        normalized_fields.append(normalized)
                    mapping['field_mappings'] = normalized_fields
            
            return result
        except Exception as e:
            return {
                'file': file_path or 'unknown',
                'mappings': [],
                'error': str(e),
                'summary': {
                    'total_mappings': 0,
                    'mapstruct_mappings': 0,
                    'pojo_mappings': 0
                }
            }
    
    def _extract_with_llm(self, code_content: str, file_path: str = None) -> Dict:
        """Extract mappings using LLM (more accurate, slower)"""
        if not self.ollama_client:
            return self._extract_with_parser(code_content, file_path)
        
        prompt = f"""Analyze this Java code and extract all field-level mappings between source and destination objects.

Code:
```java
{code_content[:8000]}  # Limit to avoid token limits
```

Extract:
1. MapStruct mappings (interfaces with @Mapper annotation)
2. POJO mappings (methods like mapXxx, convert, transform)
3. Field-level mappings (source field -> target field)
4. Any transformations or expressions

Return a JSON structure with:
- mapping_type: "mapstruct" or "pojo"
- source_type: source class name
- target_type: target class name
- method_name: method name (if applicable)
- field_mappings: [{{"source_field": "...", "target_field": "...", "transformation": "..."}}]

JSON:"""
        
        try:
            response = self.ollama_client.generate_with_llm(prompt)
            # Parse JSON response and return structured mappings
            # This is a simplified version - you might want to add more robust parsing
            import json
            try:
                mappings = json.loads(response)
                return {
                    'file': file_path or 'unknown',
                    'mappings': mappings if isinstance(mappings, list) else [mappings],
                    'summary': {
                        'total_mappings': len(mappings) if isinstance(mappings, list) else 1,
                        'mapstruct_mappings': len([m for m in (mappings if isinstance(mappings, list) else [mappings]) if m.get('mapping_type') == 'mapstruct']),
                        'pojo_mappings': len([m for m in (mappings if isinstance(mappings, list) else [mappings]) if m.get('mapping_type') == 'pojo'])
                    }
                }
            except json.JSONDecodeError:
                # Fallback to parser if LLM response is invalid
                return self._extract_with_parser(code_content, file_path)
        except Exception as e:
            # Fallback to parser on error
            return self._extract_with_parser(code_content, file_path)
    
    def extract_from_retrievals(self, code_retrievals: List[Dict], 
                                use_llm: Optional[bool] = None) -> List[Dict]:
        """Extract mappings from multiple retrieved code chunks"""
        all_mappings = []
        
        for retrieval in code_retrievals:
            code = retrieval.get('code', '') or retrieval.get('document', '')
            metadata = retrieval.get('metadata', {})
            file_path = metadata.get('file_path', 'unknown')
            
            if code:
                extracted = self.extract_from_code(code, file_path, use_llm)
                if extracted.get('mappings'):
                    all_mappings.extend(extracted['mappings'])
        
        return all_mappings

