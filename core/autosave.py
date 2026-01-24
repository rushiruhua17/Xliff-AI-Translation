import os
import json
import hashlib
import time
import shutil
import tempfile
from typing import List, Dict, Optional, Any
from core.xliff_obj import TranslationUnit
from core.logger import get_logger

logger = get_logger(__name__)

class Autosaver:
    """
    Handles atomic JSON patch creation and recovery for XLIFF files.
    """
    def __init__(self, original_file_path: str):
        self.original_path = original_file_path
        self.autosave_path = self._get_autosave_path(original_file_path)
        self.fingerprint = self.calculate_file_fingerprint(original_file_path)

    @staticmethod
    def _get_autosave_path(original_path: str) -> str:
        """Returns the expected path for the autosave file (hidden .autosave.json)."""
        dirname, filename = os.path.split(original_path)
        # e.g., f:\docs\test.xlf -> f:\docs\.test.xlf.autosave.json
        return os.path.join(dirname, f".{filename}.autosave.json")

    @staticmethod
    def calculate_file_fingerprint(file_path: str) -> str:
        """
        Calculates a quick SHA256 hash of the first 64KB of the file.
        This is used to ensure the autosave matches the file version.
        """
        if not os.path.exists(file_path):
            return ""
        
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Read first block (header/structure)
                chunk = f.read(65536) 
                sha256.update(chunk)
                # Read file size as well to avoid collisions on identical headers
                file_size = os.path.getsize(file_path)
                sha256.update(str(file_size).encode('utf-8'))
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Fingerprint calculation failed: {e}")
            return ""

    def save_patch(self, current_units: List[TranslationUnit]):
        """
        Atomically saves changes to the autosave file.
        Only saves units that have a translation (target_abstracted).
        """
        if not current_units:
            return

        # 1. Filter only translated/edited units
        patch_data = {}
        count = 0
        for unit in current_units:
            if unit.target_abstracted: # Only save if we have work
                patch_data[unit.id] = {
                    "target": unit.target_abstracted,
                    "state": unit.state,
                    "ts": time.time()
                }
                count += 1
        
        if count == 0:
            return # Nothing to save

        # 2. Construct Payload
        payload = {
            "version": "1.0",
            "original_file": self.original_path,
            "fingerprint": self.fingerprint,
            "timestamp": time.time(),
            "count": count,
            "units": patch_data
        }

        # 3. Atomic Write (Write to temp -> Rename)
        try:
            # Create a temp file in the same directory to ensure atomic move works
            dir_name = os.path.dirname(self.autosave_path)
            with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                json.dump(payload, tf, indent=2, ensure_ascii=False)
                temp_name = tf.name
            
            # Atomic replacement
            if os.path.exists(self.autosave_path):
                os.remove(self.autosave_path) # Windows replace workaround if needed, but replace is better
            
            os.replace(temp_name, self.autosave_path)
            logger.debug(f"Autosaved {count} segments to {self.autosave_path}")
            
        except Exception as e:
            logger.error(f"Autosave failed: {e}")
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)

    def check_recovery_available(self) -> Optional[Dict[str, Any]]:
        """
        Checks if a valid autosave file exists for the current original file.
        Returns the metadata dict if valid, None otherwise.
        """
        if not os.path.exists(self.autosave_path):
            return None
            
        try:
            with open(self.autosave_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validation
            if data.get("fingerprint") != self.fingerprint:
                logger.warning("Autosave fingerprint mismatch. Ignoring.")
                return None
                
            return data # Valid recovery data
            
        except Exception as e:
            logger.error(f"Corrupt autosave file found: {e}")
            return None

    def load_recovery(self) -> Dict[str, Any]:
        """Loads the full recovery payload."""
        if not os.path.exists(self.autosave_path):
            return {}
        with open(self.autosave_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def cleanup(self):
        """Removes the autosave file (e.g. after successful export or discard)."""
        if os.path.exists(self.autosave_path):
            try:
                os.remove(self.autosave_path)
                logger.info(f"Autosave cleaned up: {self.autosave_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup autosave: {e}")
