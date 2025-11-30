"""
Java Code Parser for extracting MapStruct and POJO mappings
"""
import re
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class JavaParser:
    """Parser for Java code to extract mapping information"""
    
    def __init__(self):
        self.mapstruct_patterns = {
            'mapper_interface': r'@Mapper\s*(?:\([^)]*\))?\s*(?:public\s+)?interface\s+(\w+)',
            'mapping_method': r'@Mapping\s*\([^)]*source\s*=\s*["\']([^"\']+)["\']\s*,\s*target\s*=\s*["\']([^"\']+)["\']',
            'mapping_method_simple': r'@Mapping\s*\([^)]*target\s*=\s*["\']([^"\']+)["\']',
            'method_signature': r'(\w+)\s+(\w+)\s*\([^)]*(\w+)\s+\w+[^)]*\)',
        }
        
    def parse_file(self, file_path: str) -> Dict:
        """Parse a Java file and extract mapping information"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_content(content, file_path)
    
    def parse_content(self, content: str, file_path: str = "") -> Dict:
        """Parse Java code content"""
        result = {
            'file_path': file_path,
            'mapstruct_mappings': [],
            'pojo_mappings': [],
            'classes': [],
            'interfaces': []
        }
        
        # Extract MapStruct mappings
        result['mapstruct_mappings'] = self._extract_mapstruct_mappings(content)
        
        # Extract POJO mappings
        result['pojo_mappings'] = self._extract_pojo_mappings(content)
        
        # Extract class and interface definitions
        result['classes'] = self._extract_classes(content)
        result['interfaces'] = self._extract_interfaces(content)
        
        return result
    
    def _extract_mapstruct_mappings(self, content: str) -> List[Dict]:
        """Extract MapStruct annotation mappings"""
        mappings = []
        
        # Find @Mapper interfaces
        mapper_pattern = r'@Mapper\s*(?:\([^)]*\))?\s*(?:public\s+)?interface\s+(\w+)\s*\{'
        mapper_matches = re.finditer(mapper_pattern, content, re.MULTILINE)
        
        for mapper_match in mapper_matches:
            interface_name = mapper_match.group(1)
            interface_start = mapper_match.start()
            
            # Find the end of the interface
            brace_count = 0
            in_interface = False
            interface_end = len(content)
            
            for i in range(interface_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                    in_interface = True
                elif content[i] == '}':
                    brace_count -= 1
                    if in_interface and brace_count == 0:
                        interface_end = i + 1
                        break
            
            interface_content = content[interface_start:interface_end]
            
            # Extract mapping methods - improved pattern to handle various method signatures
            # Pattern matches: ReturnType methodName(ParamType paramName);
            # Also handles generics, multiple parameters, etc.
            method_pattern = r'(\w+(?:<[^>]+>)?(?:\s*\[\])?)\s+(\w+)\s*\([^)]*\)\s*;'
            method_matches = re.finditer(method_pattern, interface_content)
            
            for method_match in method_matches:
                return_type = method_match.group(1).strip()
                method_name = method_match.group(2)
                
                # Extract parameter type from method signature
                method_full = method_match.group(0)
                param_match = re.search(r'\(([^)]+)\)', method_full)
                param_type = None
                if param_match:
                    param_str = param_match.group(1).strip()
                    # Extract first parameter type
                    param_parts = param_str.split()
                    if len(param_parts) >= 1:
                        param_type = param_parts[0].strip()
                
                # Find @Mapping annotations for this method
                method_start_in_interface = method_match.start()
                
                # Look backwards for @Mapping annotations (within interface content)
                # Search up to 50 lines before the method
                lines_before = interface_content[:method_start_in_interface].split('\n')
                annotation_lines = lines_before[-50:] if len(lines_before) > 50 else lines_before
                annotation_section = '\n'.join(annotation_lines)
                
                # Extract @Mapping annotations
                mapping_annotations = self._extract_mapping_annotations(annotation_section)
                
                if mapping_annotations:
                    for mapping in mapping_annotations:
                        mappings.append({
                            'type': 'mapstruct',
                            'interface': interface_name,
                            'method': method_name,
                            'return_type': return_type,
                            'source_type': param_type or 'Unknown',
                            'source_field': mapping.get('source'),
                            'target_field': mapping.get('target'),
                            'expression': mapping.get('expression'),
                            'qualified_by': mapping.get('qualified_by'),
                            'ignore': mapping.get('ignore', False)
                        })
                elif param_type:  # Only add implicit if we have a parameter type
                    # Implicit mapping (same field names) - create one entry per method
                    mappings.append({
                        'type': 'mapstruct',
                        'interface': interface_name,
                        'method': method_name,
                        'return_type': return_type,
                        'source_type': param_type,
                        'source_field': None,  # Will be inferred
                        'target_field': None,  # Will be inferred
                        'implicit': True
                    })
        
        return mappings
    
    def _extract_mapping_annotations(self, annotation_section: str) -> List[Dict]:
        """Extract @Mapping annotation details"""
        mappings = []
        
        # Improved pattern for @Mapping annotation - handles various formats
        # Pattern 1: @Mapping(source = "...", target = "...")
        # Pattern 2: @Mapping(target = "...")
        # Pattern 3: @Mapping(source = "...", target = "...", expression = "...")
        pattern = r'@Mapping\s*\(\s*([^)]+)\s*\)'
        
        matches = re.finditer(pattern, annotation_section, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            params_str = match.group(1)
            
            # Extract source
            source_match = re.search(r'source\s*=\s*["\']([^"\']+)["\']', params_str)
            source = source_match.group(1) if source_match else None
            
            # Extract target
            target_match = re.search(r'target\s*=\s*["\']([^"\']+)["\']', params_str)
            target = target_match.group(1) if target_match else None
            
            # Extract expression
            expr_match = re.search(r'expression\s*=\s*["\']([^"\']+)["\']', params_str)
            expression = expr_match.group(1) if expr_match else None
            
            # Extract ignore
            ignore_match = re.search(r'ignore\s*=\s*(true|false)', params_str)
            ignore = ignore_match.group(1) == 'true' if ignore_match else False
            
            # At least target should be present for a valid mapping
            if target:
                mappings.append({
                    'source': source,
                    'target': target,
                    'expression': expression,
                    'ignore': ignore
                })
        
        # Also check for @Mappings with multiple @Mapping
        mappings_pattern = r'@Mappings\s*\(\s*\{([^}]+)\}\s*\)'
        mappings_match = re.search(mappings_pattern, annotation_section, re.DOTALL)
        
        if mappings_match:
            mappings_content = mappings_match.group(1)
            inner_mappings = self._extract_mapping_annotations(mappings_content)
            mappings.extend(inner_mappings)
        
        return mappings
    
    def _extract_pojo_mappings(self, content: str) -> List[Dict]:
        """Extract POJO-based mappings (manual mapping methods)"""
        mappings = []
        
        # Pattern for mapping methods:
        # - void mapXxx(SourceType source, TargetType target)
        # - TargetType map(SourceType source)
        # - private/protected/public void mapXxx(...)
        # - Methods starting with map, convert, transform, to
        method_patterns = [
            # void mapXxx(SourceType source, TargetType target) - two params
            r'(?:private|protected|public)?\s*void\s+(map\w+)\s*\([^)]*(\w+)\s+(\w+)[^)]*,\s*(\w+)\s+(\w+)[^)]*\)\s*\{',
            # ReturnType mapXxx(SourceType source) - single param with return
            r'(?:private|protected|public)?\s*(\w+)\s+(map\w+)\s*\([^)]*(\w+)\s+(\w+)[^)]*\)\s*\{',
            # void mapXxx(SourceType source) - single param void
            r'(?:private|protected|public)?\s*void\s+(map\w+)\s*\([^)]*(\w+)\s+(\w+)[^)]*\)\s*\{',
            # ReturnType map(SourceType source) - generic map methods
            r'(?:private|protected|public)?\s*(\w+)\s+(?:map|convert|transform|to)\w*\s*\([^)]*(\w+)\s+(\w+)[^)]*\)\s*\{',
        ]
        
        for pattern in method_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                groups = match.groups()
                
                # Handle different pattern formats
                if len(groups) == 5:  # void mapXxx(SourceType source, TargetType target)
                    method_name = groups[0]
                    source_type = groups[1]
                    source_var = groups[2]
                    target_type = groups[3]
                    target_var = groups[4]
                    return_type = 'void'
                elif len(groups) == 4:  # ReturnType mapXxx(SourceType source)
                    return_type = groups[0]
                    method_name = groups[1]
                    source_type = groups[2]
                    source_var = groups[3]
                    target_type = return_type
                    target_var = None  # Will be inferred from assignments
                else:  # ReturnType map(SourceType source)
                    return_type = groups[0]
                    method_name = None
                    source_type = groups[1]
                    source_var = groups[2]
                    target_type = return_type
                    target_var = None
                
                # Find the method body
                method_start = match.end()
                brace_count = 1
                method_end = method_start
                
                for i in range(method_start, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            method_end = i + 1
                            break
                
                method_body = content[method_start:method_end]
                
                # Extract field assignments with improved detection
                if target_var:
                    field_assignments = self._extract_field_assignments_enhanced(
                        method_body, source_var, source_type, target_var, target_type
                    )
                else:
                    # Fallback to original extraction
                    field_assignments = self._extract_field_assignments(method_body, source_var, target_type)
                
                if field_assignments:
                    mappings.append({
                        'type': 'pojo',
                        'method': method_name,
                        'return_type': return_type,
                        'source_type': source_type,
                        'target_type': target_type,
                        'mappings': field_assignments
                    })
        
        return mappings
    
    def _extract_field_assignments_enhanced(self, method_body: str, source_var: str, source_type: str,
                                            target_var: str, target_type: str) -> List[Dict]:
        """Extract field assignments from method body with enhanced detection"""
        assignments = []
        
        # Pattern 1: target.setField(source.getField())
        setter_pattern = r'(\w+)\.set(\w+)\s*\(\s*' + re.escape(source_var) + r'\.get(\w+)\s*\(\)\s*\)'
        matches = re.finditer(setter_pattern, method_body)
        
        for match in matches:
            target_var_name = match.group(1)
            target_field = match.group(2)
            source_field = match.group(3)
            
            # Convert to camelCase
            target_field = target_field[0].lower() + target_field[1:] if target_field else target_field
            source_field = source_field[0].lower() + source_field[1:] if source_field else source_field
            
            assignments.append({
                'source_field': source_field,
                'target_field': target_field,
                'target_path': f"{target_var_name}.{target_field}" if target_var_name != target_var else target_field
            })
        
        # Pattern 2: target.field = source.field
        direct_pattern = r'(\w+)\.(\w+)\s*=\s*' + re.escape(source_var) + r'\.(\w+)'
        matches = re.finditer(direct_pattern, method_body)
        
        for match in matches:
            target_var_name = match.group(1)
            target_field = match.group(2)
            source_field = match.group(3)
            
            assignments.append({
                'source_field': source_field,
                'target_field': target_field,
                'target_path': f"{target_var_name}.{target_field}" if target_var_name != target_var else target_field
            })
        
        # Pattern 3: Nested assignments like note.setNoteType(VALUE) where note is created and added to target
        # Example: note.setNoteType(NOTE_TYPE_CUSTOMER_COMMENT); orderLine.setNotes(notes);
        # Track local variables that are created and then added to target
        if target_var:
            # First, build a map of local variables to their source expressions
            # Pattern: instanceof String orderLineComment or String varName = source.getX()
            local_var_sources = {}
            
            # Pattern: source.getX().get(Y) instanceof String localVar
            # More flexible pattern to catch: purchaseLineItem.getMiscAttributes().get(SPECIAL_INSTRUCTIONS) instanceof String orderLineComment
            instanceof_pattern = rf'{re.escape(source_var)}\.[^&]+instanceof\s+\w+\s+(\w+)'
            instanceof_matches = re.finditer(instanceof_pattern, method_body, re.DOTALL)
            for im in instanceof_matches:
                local_var = im.group(1)
                full_match = im.group(0)
                # Extract the source path - look for getMiscAttributes().get(...)
                if "getMiscAttributes" in full_match:
                    # Extract what's inside .get(...) - could be SPECIAL_INSTRUCTIONS constant
                    get_matches = list(re.finditer(r'\.get\(([^)]+)\)', full_match))
                    if get_matches:
                        # Get the last .get() call which is the key
                        key = get_matches[-1].group(1)
                        # Convert constant like SPECIAL_INSTRUCTIONS to camelCase specialInstructions
                        if '_' in key:
                            parts = key.lower().split('_')
                            camel_key = parts[0] + ''.join(p.capitalize() for p in parts[1:])
                        else:
                            camel_key = key.lower()
                        local_var_sources[local_var] = f"miscAttributes.{camel_key}"
                    else:
                        local_var_sources[local_var] = "miscAttributes"
                else:
                    # Extract source field from nested_value
                    source_path_match = re.search(rf'{re.escape(source_var)}\.get(\w+)\s*\(\)', full_match)
                    if source_path_match:
                        base_field = source_path_match.group(1)
                        local_var_sources[local_var] = base_field[0].lower() + base_field[1:] if base_field else "unknown"
            
            # Pattern: localVar = source.getX()
            assignment_pattern = rf'(\w+)\s*=\s*{re.escape(source_var)}\.get(\w+)\s*\(\)'
            assignment_matches = re.finditer(assignment_pattern, method_body)
            for am in assignment_matches:
                local_var = am.group(1)
                source_field = am.group(2)
                local_var_sources[local_var] = source_field[0].lower() + source_field[1:] if source_field else source_field
            
            # Find: target.setField(localVar) or target.getField().add(localVar)
            # Pattern should capture: orderLine.setNotes(notes) -> field=Notes, var=notes
            target_setter_pattern = rf'{re.escape(target_var)}\.set(\w+)\s*\(\s*(\w+)\s*\)'
            target_matches = re.finditer(target_setter_pattern, method_body)
            
            # Track variables that are added to lists: listVar.add(itemVar)
            # This helps us find nested objects in collections
            list_items = {}  # Maps list variable to list of item variables
            list_add_pattern = r'(\w+)\.add\s*\((\w+)\)'
            list_add_matches = re.finditer(list_add_pattern, method_body)
            for lam in list_add_matches:
                list_var = lam.group(1)
                item_var = lam.group(2)
                if list_var not in list_items:
                    list_items[list_var] = []
                list_items[list_var].append(item_var)
            
            for target_match in target_matches:
                target_field = target_match.group(1)
                local_var = target_match.group(2)
                
                # Check if local_var is a list that contains items
                item_vars = list_items.get(local_var, [])
                
                # Find all setter calls on items in the list (like note.setNoteType(...))
                # Also check the list variable itself in case it's not a list
                all_vars_to_check = item_vars if item_vars else [local_var]
                local_setters = []
                for item_var in all_vars_to_check:
                    local_var_pattern = rf'{re.escape(item_var)}\.set(\w+)\s*\(([^)]+)\)'
                    for setter_match in re.finditer(local_var_pattern, method_body):
                        local_setters.append((item_var, setter_match, item_var in item_vars))
                
                for item_var, setter_match, is_list_item in local_setters:
                    nested_field = setter_match.group(1)
                    nested_value = setter_match.group(2).strip()
                    
                    # Determine source field
                    source_field = None
                    if source_var in nested_value:
                        # Extract source field from nested_value
                        source_field_match = re.search(rf'{re.escape(source_var)}\.get(\w+)\s*\(\)', nested_value)
                        if source_field_match:
                            source_field = source_field_match.group(1)
                            source_field = source_field[0].lower() + source_field[1:] if source_field else source_field
                        elif "getMiscAttributes" in nested_value:
                            # Complex path like getMiscAttributes().get(SPECIAL_INSTRUCTIONS)
                            source_field = "miscAttributes.specialInstructions"
                        else:
                            source_field = "unknown"
                    elif nested_value in local_var_sources:
                        # Local variable that was assigned from source
                        source_field = local_var_sources[nested_value]
                    else:
                        # Constant or expression - check if it's a constant (all caps with underscores)
                        clean_value = nested_value.strip()
                        if re.match(r'^[A-Z_][A-Z0-9_]*$', clean_value):
                            # It's a constant like NOTE_TYPE_CUSTOMER_COMMENT
                            # Mark it as a constant but keep the value for reference
                            source_field = f"constant:{clean_value}"
                        elif len(clean_value) < 50 and not clean_value.startswith('new '):
                            source_field = clean_value
                        else:
                            source_field = "constant"
                    
                    target_field_camel = target_field[0].lower() + target_field[1:] if target_field else target_field
                    nested_field_camel = nested_field[0].lower() + nested_field[1:] if nested_field else nested_field
                    
                    # Build target path - if it's a list item, use [] notation
                    if is_list_item:
                        target_path = f"{target_var}.{target_field_camel}[].{nested_field_camel}"
                        target_field_path = f"{target_field_camel}[].{nested_field_camel}"
                    else:
                        target_path = f"{target_var}.{target_field_camel}.{nested_field_camel}"
                        target_field_path = f"{target_field_camel}.{nested_field_camel}"
                    
                    assignments.append({
                        'source_field': source_field or "unknown",
                        'target_field': target_field_path,
                        'target_path': target_path,
                        'value': nested_value[:100] if len(nested_value) < 100 else nested_value[:100] + "..."
                    })
                    
                    # Also extract if nested_value comes from source (like purchaseLineItem.getCreatedDate())
                    if source_var in nested_value:
                        source_getter_match = re.search(rf'{re.escape(source_var)}\.get(\w+)\s*\(\)', nested_value)
                        if source_getter_match:
                            direct_source_field = source_getter_match.group(1)
                            direct_source_field = direct_source_field[0].lower() + direct_source_field[1:] if direct_source_field else direct_source_field
                            assignments.append({
                                'source_field': direct_source_field,
                                'target_field': f"{target_field_camel}[].{nested_field_camel}",
                                'target_path': f"{target_var}.{target_field_camel}[].{nested_field_camel}",
                                'value': nested_value[:100]
                            })
        
        # Pattern 4: Complex nested paths like purchaseLineItem.getMiscAttributes().get(SPECIAL_INSTRUCTIONS)
        # Extract these as source fields
        complex_source_pattern = rf'{re.escape(source_var)}\.get(\w+)\s*\(\)(?:\.get\([^)]+\))?'
        complex_matches = re.finditer(complex_source_pattern, method_body)
        
        for complex_match in complex_matches:
            base_field = complex_match.group(1)
            base_field = base_field[0].lower() + base_field[1:] if base_field else base_field
            
            # Find where this is used in target assignments
            # This is a simplified extraction - full implementation would need AST parsing
            pass
        
        # Pattern 5: Direct constant assignments to target fields
        # Like: note.setNoteType(NOTE_TYPE_CUSTOMER_COMMENT)
        # We already handle this in Pattern 3, but let's also track direct assignments
        constant_setter_pattern = r'(\w+)\.set(\w+)\s*\(([^)]+)\)'
        constant_matches = re.finditer(constant_setter_pattern, method_body)
        
        for const_match in constant_matches:
            var_name = const_match.group(1)
            field_name = const_match.group(2)
            value = const_match.group(3).strip()
            
            # If this variable is later assigned to target, track it
            # Check if var_name is added to target
            if var_name not in [source_var, 'this'] and len(value) < 100:
                field_camel = field_name[0].lower() + field_name[1:] if field_name else field_name
                # This will be linked to target in Pattern 3 above
                pass
        
        return assignments
    
    def _extract_field_assignments(self, method_body: str, source_var: str, target_type: str) -> List[Dict]:
        """Extract field assignments from method body (original method for backward compatibility)"""
        assignments = []
        
        # Pattern 1: target.setField(source.getField())
        setter_pattern = r'(\w+)\.set(\w+)\s*\(\s*' + re.escape(source_var) + r'\.get(\w+)\s*\(\)\s*\)'
        matches = re.finditer(setter_pattern, method_body)
        
        for match in matches:
            target_var = match.group(1)
            target_field = match.group(2)
            source_field = match.group(3)
            
            # Convert to camelCase
            target_field = target_field[0].lower() + target_field[1:] if target_field else target_field
            source_field = source_field[0].lower() + source_field[1:] if source_field else source_field
            
            assignments.append({
                'source_field': source_field,
                'target_field': target_field
            })
        
        # Pattern 2: target.field = source.field
        direct_pattern = r'(\w+)\.(\w+)\s*=\s*' + re.escape(source_var) + r'\.(\w+)'
        matches = re.finditer(direct_pattern, method_body)
        
        for match in matches:
            target_var = match.group(1)
            target_field = match.group(2)
            source_field = match.group(3)
            
            assignments.append({
                'source_field': source_field,
                'target_field': target_field
            })
        
        return assignments
    
    def _extract_classes(self, content: str) -> List[Dict]:
        """Extract class definitions"""
        classes = []
        pattern = r'(?:public\s+)?(?:final\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[^{]+)?\s*\{'
        
        matches = re.finditer(pattern, content)
        for match in matches:
            classes.append({
                'name': match.group(1),
                'position': match.start()
            })
        
        return classes
    
    def _extract_interfaces(self, content: str) -> List[Dict]:
        """Extract interface definitions"""
        interfaces = []
        pattern = r'(?:public\s+)?interface\s+(\w+)(?:\s+extends\s+[^{]+)?\s*\{'
        
        matches = re.finditer(pattern, content)
        for match in matches:
            interfaces.append({
                'name': match.group(1),
                'position': match.start()
            })
        
        return interfaces
    
    def find_java_files(self, path: str, recursive: bool = True, extensions: List[str] = None, 
                       exclude_patterns: List[str] = None) -> List[str]:
        """Find all Java files in a directory, excluding specified patterns"""
        if extensions is None:
            extensions = ['.java']
        
        if exclude_patterns is None:
            exclude_patterns = []
        
        java_files = []
        path_obj = Path(path)
        
        if path_obj.is_file() and path_obj.suffix in extensions:
            # Check if file should be excluded
            if not self._should_exclude_file(str(path_obj), exclude_patterns):
                return [str(path_obj)]
            return []
        
        if path_obj.is_dir():
            if recursive:
                for ext in extensions:
                    all_files = path_obj.rglob(f'*{ext}')
                    for file_path in all_files:
                        # Early exclusion check for better performance
                        if not self._should_exclude_file(str(file_path), exclude_patterns):
                            java_files.append(file_path)
            else:
                for ext in extensions:
                    all_files = path_obj.glob(f'*{ext}')
                    for file_path in all_files:
                        if not self._should_exclude_file(str(file_path), exclude_patterns):
                            java_files.append(file_path)
        
        return [str(f) for f in java_files]
    
    def _should_exclude_file(self, file_path: str, exclude_patterns: List[str]) -> bool:
        """Check if a file should be excluded based on patterns"""
        from fnmatch import fnmatch
        
        # Normalize path separators
        normalized_path = file_path.replace('\\', '/')
        
        for pattern in exclude_patterns:
            # Convert glob pattern to match against path
            # Handle ** patterns
            if '**' in pattern:
                # Convert ** pattern to regex-like matching
                pattern_parts = pattern.split('**')
                if len(pattern_parts) == 2:
                    # Pattern like "**/target/**"
                    if pattern_parts[0] and not normalized_path.startswith(pattern_parts[0].lstrip('/')):
                        continue
                    if pattern_parts[1] and not normalized_path.endswith(pattern_parts[1].rstrip('/')):
                        continue
                    # Check if any part of the path matches
                    if pattern_parts[0].lstrip('/') in normalized_path or pattern_parts[1].rstrip('/') in normalized_path:
                        return True
                else:
                    # Simple ** pattern
                    if fnmatch(normalized_path, pattern) or pattern.replace('**', '*') in normalized_path:
                        return True
            else:
                # Simple pattern matching
                if fnmatch(normalized_path, pattern) or pattern in normalized_path:
                    return True
        
        return False

