#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot ingestion issues
"""
import sys
from main import CodeUnderstandingSME
from pathlib import Path

def diagnose():
    print("="*80)
    print("AI Code Understanding SME - Diagnostic Tool")
    print("="*80)
    print()
    
    # Initialize SME
    sme = CodeUnderstandingSME()
    
    # Check 1: Configuration
    print("1. Checking Configuration...")
    projects = sme.config.get('input', {}).get('projects', [])
    codebase_path = sme.config.get('input', {}).get('codebase_path', '')
    
    if projects:
        print(f"   ✓ Found {len(projects)} project(s) configured")
        for i, project in enumerate(projects, 1):
            path = Path(project)
            if path.exists():
                print(f"   ✓ Project {i}: {project} (exists)")
            else:
                print(f"   ✗ Project {i}: {project} (NOT FOUND)")
    elif codebase_path:
        print(f"   ✓ Codebase path: {codebase_path}")
        if Path(codebase_path).exists():
            print(f"   ✓ Path exists")
        else:
            print(f"   ✗ Path does not exist")
    else:
        print("   ✗ No projects or codebase_path configured")
        return
    
    print()
    
    # Check 2: Ollama
    print("2. Checking Ollama Connection...")
    if sme.ollama_client:
        if sme.ollama_client.check_connection():
            print("   ✓ Ollama is running")
            print(f"   ✓ Embeddings model: {sme.ollama_client.model}")
        else:
            print("   ✗ Ollama is not running or model not available")
            print(f"   → Run: ollama pull {sme.ollama_client.model}")
    else:
        print("   ⚠ Ollama client not initialized (embeddings disabled?)")
    
    print()
    
    # Check 3: Vector DB
    print("3. Checking Vector Database...")
    if sme.vector_db:
        print("   ✓ Vector DB initialized")
        stats = sme.vector_db.get_stats()
        print(f"   → Total mappings: {stats.get('total_mappings', 0)}")
        if stats.get('mapping_types'):
            for mtype, count in stats['mapping_types'].items():
                print(f"   → {mtype}: {count}")
    else:
        print("   ✗ Vector DB not initialized")
        print("   → Check vector_db.enabled in config.yaml")
    
    print()
    
    # Check 4: Test file discovery
    print("4. Testing File Discovery...")
    if projects:
        test_project = projects[0]
    elif codebase_path:
        test_project = codebase_path
    else:
        print("   ✗ No project to test")
        return
    
    test_path = Path(test_project)
    if test_path.exists():
        exclude_patterns = sme.config.get('input', {}).get('exclude_patterns', [])
        java_files = sme.parser.find_java_files(
            str(test_path),
            recursive=True,
            extensions=['.java'],
            exclude_patterns=exclude_patterns
        )
        print(f"   ✓ Found {len(java_files):,} Java file(s)")
        if len(java_files) > 0:
            print(f"   → Sample file: {java_files[0]}")
        else:
            print("   ⚠ No Java files found (check exclude_patterns)")
    else:
        print(f"   ✗ Project path does not exist: {test_project}")
    
    print()
    
    # Check 5: Test mapping extraction
    print("5. Testing Mapping Extraction...")
    if projects or codebase_path:
        test_path = Path(projects[0] if projects else codebase_path)
        if test_path.exists():
            exclude_patterns = sme.config.get('input', {}).get('exclude_patterns', [])
            java_files = sme.parser.find_java_files(
                str(test_path),
                recursive=True,
                extensions=['.java'],
                exclude_patterns=exclude_patterns
            )
            
            if len(java_files) > 0:
                # Test first 5 files
                test_files = java_files[:5]
                total_mappings = 0
                files_with_mappings = 0
                
                for test_file in test_files:
                    try:
                        result = sme.extractor.extract_mappings(test_file)
                        num_mappings = len(result.get('mappings', []))
                        if num_mappings > 0:
                            files_with_mappings += 1
                            total_mappings += num_mappings
                            print(f"   ✓ {Path(test_file).name}: {num_mappings} mapping(s)")
                        else:
                            print(f"   ℹ {Path(test_file).name}: No mappings found")
                    except Exception as e:
                        print(f"   ✗ {Path(test_file).name}: Error - {e}")
                
                print(f"   → Summary: {files_with_mappings}/{len(test_files)} files have mappings")
                print(f"   → Total mappings in sample: {total_mappings}")
                
                if total_mappings == 0:
                    print("   ⚠ WARNING: No mappings found in sample files!")
                    print("   → This could mean:")
                    print("     - Files don't contain MapStruct or POJO mappings")
                    print("     - Parser patterns need adjustment")
                    print("     - Files are excluded by patterns")
            else:
                print("   ✗ No Java files to test")
    
    print()
    print("="*80)
    print("Diagnostic Complete")
    print("="*80)
    print()
    print("Next Steps:")
    print("1. If no mappings found, test a specific file:")
    print("   python main.py --test-file <path-to-java-file>")
    print()
    print("2. If Ollama not working, check:")
    print("   python main.py --check-ollama")
    print()
    print("3. To see verbose output during ingestion:")
    print("   python main.py --process-codebase --verbose")

if __name__ == '__main__':
    diagnose()

