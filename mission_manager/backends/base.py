from abc import ABC, abstractmethod
from typing import Optional

class InferenceBackend(ABC):
    """Abstract base class for all inference backends."""

    @abstractmethod
    def generate(self,
                 system_prompt: str,
                 user_prompt: str,
                 image_b64: Optional[str] = None) -> str:
        """
        Generate a response from the model.
        
        Args:
            system_prompt: System context and instructions
            user_prompt: User message for this inference call
            image_b64: Optional base64 encoded image
            
        Returns:
            Raw text response from the model
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the backend is available and ready.
        
        Returns:
            True if ready, False otherwise
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this backend for logging."""
        pass