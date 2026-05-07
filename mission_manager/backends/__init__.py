import os
from backends.base import InferenceBackend

def load_backend() -> InferenceBackend:
    backend_type = os.getenv('INFERENCE_BACKEND', 'vila').lower()

    if backend_type == 'ollama':
        from backends.ollama_backend import OllamaBackend
        return OllamaBackend(
            host=os.getenv('OLLAMA_HOST', 'localhost'),
            port=int(os.getenv('OLLAMA_PORT', '11434')),
            model=os.getenv('OLLAMA_MODEL', 'llama3.2:1b')
        )
    elif backend_type == 'vila':
        from backends.vila_backend import VILABackend
        return VILABackend(
            host=os.getenv('VILA_HOST', 'localhost'),
            port=int(os.getenv('VILA_PORT', '5000'))
        )
    elif backend_type == 'tensorrt':
        from backends.tensorrt_backend import TensorRTBackend
        return TensorRTBackend(
            host=os.getenv('TENSORRT_HOST', 'localhost'),
            port=int(os.getenv('TENSORRT_PORT', '8000')),
            model=os.getenv('TENSORRT_MODEL', 'vila')
        )
    else:
        raise ValueError(f"Unknown backend: {backend_type}. Choose: ollama, vila, tensorrt")