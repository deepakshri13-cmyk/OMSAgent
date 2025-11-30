"""
Mapping Extractor - Extracts source to destination field-level mappings
"""
from typing import List, Dict, Optional
from java_parser import JavaParser


class MappingExtractor:
    """Extracts and structures field-level mappings from Java code"""
    
    def __init__(self, parser: JavaParser):
        self.parser = parser
    
    def extract_mappings(self, file_path: str) -> Dict:
        """Extract all mappings from a Java file"""
        parsed_data = self.parser.parse_file(file_path)
        
        result = {
            'file': file_path,
            'mappings': [],
            'summary': {
                'total_mappings': 0,
                'mapstruct_mappings': 0,
                'pojo_mappings': 0
            }
        }
        
        # Process MapStruct mappings
        for mapstruct_mapping in parsed_data['mapstruct_mappings']:
            mapping_entry = {
                'type': 'mapstruct',
                'interface': mapstruct_mapping.get('interface'),
                'method': mapstruct_mapping.get('method'),
                'source_type': mapstruct_mapping.get('source_type'),
                'target_type': mapstruct_mapping.get('return_type'),
                'field_mappings': []
            }
            
            if mapstruct_mapping.get('source_field') and mapstruct_mapping.get('target_field'):
                mapping_entry['field_mappings'].append({
                    'source': mapstruct_mapping['source_field'],
                    'target': mapstruct_mapping['target_field'],
                    'expression': mapstruct_mapping.get('expression'),
                    'ignore': mapstruct_mapping.get('ignore', False)
                })
            elif mapstruct_mapping.get('implicit'):
                # For implicit mappings, we'd need to analyze the types
                # This is a placeholder - would need type analysis
                mapping_entry['implicit'] = True
            
            if mapping_entry['field_mappings'] or mapping_entry.get('implicit'):
                result['mappings'].append(mapping_entry)
                result['summary']['mapstruct_mappings'] += 1
        
        # Process POJO mappings
        for pojo_mapping in parsed_data['pojo_mappings']:
            if pojo_mapping.get('mappings'):
                mapping_entry = {
                    'type': 'pojo',
                    'source_type': pojo_mapping.get('source_type'),
                    'target_type': pojo_mapping.get('return_type'),
                    'field_mappings': pojo_mapping['mappings']
                }
                
                result['mappings'].append(mapping_entry)
                result['summary']['pojo_mappings'] += 1
        
        result['summary']['total_mappings'] = len(result['mappings'])
        
        return result
    
    def extract_mappings_from_content(self, content: str, file_path: str = "") -> Dict:
        """Extract mappings from Java code content string"""
        parsed_data = self.parser.parse_content(content, file_path)
        
        result = {
            'file': file_path or 'inline',
            'mappings': [],
            'summary': {
                'total_mappings': 0,
                'mapstruct_mappings': 0,
                'pojo_mappings': 0
            }
        }
        
        # Process MapStruct mappings
        for mapstruct_mapping in parsed_data['mapstruct_mappings']:
            mapping_entry = {
                'type': 'mapstruct',
                'interface': mapstruct_mapping.get('interface'),
                'method': mapstruct_mapping.get('method'),
                'source_type': mapstruct_mapping.get('source_type'),
                'target_type': mapstruct_mapping.get('return_type'),
                'field_mappings': []
            }
            
            if mapstruct_mapping.get('source_field') and mapstruct_mapping.get('target_field'):
                mapping_entry['field_mappings'].append({
                    'source': mapstruct_mapping['source_field'],
                    'target': mapstruct_mapping['target_field'],
                    'expression': mapstruct_mapping.get('expression'),
                    'ignore': mapstruct_mapping.get('ignore', False)
                })
            elif mapstruct_mapping.get('implicit'):
                mapping_entry['implicit'] = True
            
            if mapping_entry['field_mappings'] or mapping_entry.get('implicit'):
                result['mappings'].append(mapping_entry)
                result['summary']['mapstruct_mappings'] += 1
        
        # Process POJO mappings
        for pojo_mapping in parsed_data['pojo_mappings']:
            if pojo_mapping.get('mappings'):
                mapping_entry = {
                    'type': 'pojo',
                    'source_type': pojo_mapping.get('source_type'),
                    'target_type': pojo_mapping.get('return_type'),
                    'field_mappings': pojo_mapping['mappings']
                }
                
                result['mappings'].append(mapping_entry)
                result['summary']['pojo_mappings'] += 1
        
        result['summary']['total_mappings'] = len(result['mappings'])
        
        return result
    
    def format_mappings(self, mappings_data: Dict, format: str = 'json') -> str:
        """Format mappings in the specified output format"""
        if format == 'text':
            return self._format_text(mappings_data)
        elif format == 'yaml':
            import yaml
            return yaml.dump(mappings_data, default_flow_style=False, sort_keys=False)
        else:  # json
            import json
            return json.dumps(mappings_data, indent=2)
    
    def _format_text(self, mappings_data: Dict) -> str:
        """Format mappings as human-readable text"""
        lines = []
        lines.append(f"File: {mappings_data['file']}")
        lines.append(f"Total Mappings: {mappings_data['summary']['total_mappings']}")
        lines.append(f"  - MapStruct: {mappings_data['summary']['mapstruct_mappings']}")
        lines.append(f"  - POJO: {mappings_data['summary']['pojo_mappings']}")
        lines.append("")
        
        for i, mapping in enumerate(mappings_data['mappings'], 1):
            lines.append(f"Mapping {i}: {mapping['type'].upper()}")
            lines.append(f"  Source Type: {mapping.get('source_type', 'N/A')}")
            lines.append(f"  Target Type: {mapping.get('target_type', 'N/A')}")
            
            if mapping.get('interface'):
                lines.append(f"  Interface: {mapping['interface']}")
            if mapping.get('method'):
                lines.append(f"  Method: {mapping['method']}")
            
            if mapping.get('field_mappings'):
                lines.append("  Field Mappings:")
                for fm in mapping['field_mappings']:
                    source = fm.get('source', 'N/A')
                    target = fm.get('target', 'N/A')
                    lines.append(f"    {source} -> {target}")
                    if fm.get('expression'):
                        lines.append(f"      Expression: {fm['expression']}")
                    if fm.get('ignore'):
                        lines.append(f"      (IGNORED)")
            elif mapping.get('implicit'):
                lines.append("  Implicit mapping (field names match)")
            
            lines.append("")
        
        return "\n".join(lines)

