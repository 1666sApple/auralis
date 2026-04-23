import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)

class SchemaLoader:
    """
    Dedicated loader for reading JSON schema files from `src/generator/prompts/json_schema/`.
    """
    
    def __init__(self, schema_dir: Optional[str] = None):
        if schema_dir is None:
            self.schema_dir = Path(__file__).parent.parent / "json_schema"
        else:
            self.schema_dir = Path(schema_dir)
            
        self._cache: Dict[str, str] = {}
        
    def get_schema(self, schema_filename: str) -> str:
        """
        Loads the schema file as a string. Caches the result to avoid repeated disk reads.
        
        Args:
            schema_filename: The name of the schema file (e.g., 'cv_schema.json').
            
        Returns:
            The raw JSON schema string.
        """
        if schema_filename in self._cache:
            return self._cache[schema_filename]
            
        schema_path = self.schema_dir / schema_filename
        
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Validate it's parseable JSON just in case
                json.loads(content) 
                
                self._cache[schema_filename] = content
                return content
        except FileNotFoundError:
            logger.error(f"Schema file not found at {schema_path}")
            return "{}"
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse schema {schema_filename} as valid JSON: {e}")
            return "{}"
            
    def reload(self) -> None:
        """Clears the cache to force a fresh read from disk."""
        self._cache.clear()
