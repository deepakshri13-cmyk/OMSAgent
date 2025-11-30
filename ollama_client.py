"""
Ollama Client for Jina Embeddings
"""
import requests
import json
import time
import threading
from typing import List, Optional, Dict


class OllamaClient:
    """Client for interacting with Ollama API for embeddings"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text",
                 max_concurrent_requests: int = 2):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.embeddings_endpoint = f"{self.base_url}/api/embeddings"
        self.generate_endpoint = f"{self.base_url}/api/generate"
        # Semaphore to limit concurrent requests to Ollama (prevents overwhelming it)
        self._request_semaphore = threading.Semaphore(max_concurrent_requests)
    
    def check_connection(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                return any(self.model in name for name in model_names)
            return False
        except Exception as e:
            print(f"Error checking Ollama connection: {e}")
            return False
    
    def get_embeddings(self, text: str, max_retries: int = 3) -> Optional[List[float]]:
        """Get embeddings for a text string with retry logic and size limits"""
        if not text or not text.strip():
            return None
        
        # Limit text size to prevent EOF errors (Jina embeddings have issues with large chunks)
        # Use smaller limit: ~2000 characters to be safe
        max_text_length = 2000
        if len(text) > max_text_length:
            # Truncate and add indicator
            text = text[:max_text_length] + "\n[... truncated for embedding ...]"
        
        for attempt in range(max_retries):
            # Use semaphore to limit concurrent requests (prevents overwhelming Ollama)
            with self._request_semaphore:
                try:
                    payload = {
                        "model": self.model,
                        "prompt": text
                    }
                    
                    # Use shorter timeout to fail fast
                    timeout = 10
                    
                    response = requests.post(
                        self.embeddings_endpoint,
                        json=payload,
                        timeout=timeout
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        embedding = result.get('embedding')
                        if embedding:
                            return embedding
                        else:
                            if attempt < max_retries - 1:
                                time.sleep(0.5)
                                continue
                            return None
                    else:
                        error_msg = response.text
                        # Check if Ollama crashed or is overwhelmed
                        if "llama runner process no longer running" in error_msg or "process" in error_msg.lower():
                            if attempt < max_retries - 1:
                                # Wait longer before retry (Ollama may need to restart)
                                wait_time = 1.5 * (attempt + 1)  # Exponential backoff: 1.5s, 3s, 4.5s
                                time.sleep(wait_time)
                                continue
                            else:
                                # Don't print on final attempt to reduce noise
                                return None
                        # Check if it's a model-specific error
                        elif "embedding" in error_msg.lower() and "EOF" in error_msg:
                            if attempt < max_retries - 1:
                                # Try with even smaller text on retry
                                if len(text) > 1000:
                                    text = text[:1000] + "\n[... truncated ...]"
                                time.sleep(0.5)
                                continue
                            else:
                                return None
                        else:
                            if attempt < max_retries - 1:
                                time.sleep(1.0)
                                continue
                            else:
                                return None
                            
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        time.sleep(1.0)
                        continue
                    else:
                        return None
                except requests.exceptions.ConnectionError as e:
                    if attempt < max_retries - 1:
                        # Wait longer for connection errors (Ollama may be restarting)
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    else:
                        return None
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    else:
                        return None
        
        return None
    
    def get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Get embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            emb = self.get_embeddings(text)
            embeddings.append(emb)
        return embeddings
    
    def generate_embedding_description(self, code_snippet: str, mapping_info: Dict) -> Optional[str]:
        """Use Ollama to generate a description of the mapping using embeddings context"""
        try:
            # Create a prompt that describes the mapping
            prompt = f"""Analyze this Java code mapping and provide a clear description:

Code:
{code_snippet}

Mapping Information:
{json.dumps(mapping_info, indent=2)}

Provide a concise description of what this mapping does."""
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(
                self.generate_endpoint,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                return None
        except Exception as e:
            print(f"Error generating description: {e}")
            return None
    
    def enhance_mapping_understanding(self, code: str, mappings: List[Dict]) -> List[Dict]:
        """Enhance mappings with embedding-based understanding"""
        enhanced_mappings = []
        
        for mapping in mappings:
            # Create a context string from the mapping
            context = f"Mapping from {mapping.get('source_type')} to {mapping.get('target_type')}"
            if mapping.get('field_mappings'):
                context += f" with {len(mapping['field_mappings'])} field mappings"
            
            # Get embedding for the mapping context
            embedding = self.get_embeddings(context)
            
            enhanced_mapping = mapping.copy()
            if embedding:
                enhanced_mapping['embedding_context'] = context
                enhanced_mapping['has_embedding'] = True
            
            enhanced_mappings.append(enhanced_mapping)
        
        return enhanced_mappings
    
    def pull_model(self) -> bool:
        """Pull the model from Ollama if not available"""
        try:
            import subprocess
            result = subprocess.run(
                ['ollama', 'pull', self.model],
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error pulling model: {e}")
            print(f"Please run manually: ollama pull {self.model}")
            return False
    
    def generate_with_llm(self, prompt: str, model: str = "qwen2.5-coder:7b", 
                          stream: bool = False, system: Optional[str] = None) -> Optional[str]:
        """Generate text using an LLM model (e.g., Qwen2.5-Coder)"""
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }
            
            if system:
                payload["system"] = system
            
            response = requests.post(
                self.generate_endpoint,
                json=payload,
                timeout=120,
                stream=stream
            )
            
            if response.status_code == 200:
                if stream:
                    # For streaming, return the response object
                    return response
                else:
                    result = response.json()
                    return result.get('response', '')
            else:
                print(f"Error generating with LLM: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Exception generating with LLM: {e}")
            return None
    
    def check_llm_model(self, model: str = "qwen2.5-coder:7b") -> bool:
        """Check if an LLM model is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                return any(model in name or name in model for name in model_names)
            return False
        except Exception as e:
            print(f"Error checking LLM model: {e}")
            return False

