from PyQt6.QtCore import QSettings

class AppConfig:
    """
    Centralized configuration management.
    Wraps QSettings to provide type-safe access to application settings.
    """
    def __init__(self):
        self.settings = QSettings("MyCompany", "XLIFF_AI_Assistant")

    @property
    def source_lang(self) -> str:
        return self.settings.value("source_lang", "zh-CN")

    @source_lang.setter
    def source_lang(self, value: str):
        self.settings.setValue("source_lang", value)

    @property
    def target_lang(self) -> str:
        return self.settings.value("target_lang", "en")

    @target_lang.setter
    def target_lang(self, value: str):
        self.settings.setValue("target_lang", value)

    @property
    def geometry(self):
        return self.settings.value("geometry")

    @geometry.setter
    def geometry(self, value):
        self.settings.setValue("geometry", value)

    @property
    def theme(self) -> str:
        return self.settings.value("theme", "dark")

    @theme.setter
    def theme(self, value: str):
        self.settings.setValue("theme", value)

    @property
    def auto_repair_enabled(self) -> bool:
        return self.settings.value("auto_repair_enabled", False, type=bool)

    @auto_repair_enabled.setter
    def auto_repair_enabled(self, value: bool):
        self.settings.setValue("auto_repair_enabled", value)

    @property
    def diagnostic_mode(self) -> bool:
        return self.settings.value("diagnostic_mode", False, type=bool)

    @diagnostic_mode.setter
    def diagnostic_mode(self, value: bool):
        self.settings.setValue("diagnostic_mode", value)

    # --- Model Registry System ---
    
    @property
    def model_profiles(self) -> list:
        """
        Returns a list of dicts:
        [
            {"id": "uuid1", "name": "DeepSeek Main", "provider": "custom", "api_key": "...", "base_url": "...", "model": "..."},
            ...
        ]
        """
        # QSettings can store lists if using INI, but JSON serialization is safer for complex structures
        import json
        raw = self.settings.value("model_profiles", "[]")
        try:
            return json.loads(raw)
        except:
            return []

    @model_profiles.setter
    def model_profiles(self, profiles: list):
        import json
        self.settings.setValue("model_profiles", json.dumps(profiles))

    @property
    def task_mappings(self) -> dict:
        """
        Maps task names to profile IDs.
        {
            "translation": "uuid1",
            "repair": "uuid2",
            "profile_analysis": "uuid1"
        }
        """
        import json
        raw = self.settings.value("task_mappings", "{}")
        try:
            return json.loads(raw)
        except:
            return {}

    @task_mappings.setter
    def task_mappings(self, mappings: dict):
        import json
        self.settings.setValue("task_mappings", json.dumps(mappings))
        
    def get_profile_by_task(self, task_name: str) -> dict:
        """Helper to resolve full profile config for a given task."""
        mappings = self.task_mappings
        profile_id = mappings.get(task_name)
        if not profile_id: return None
        
        for p in self.model_profiles:
            if p["id"] == profile_id:
                return p
        return None

    def sync(self):
        self.settings.sync()

    @property
    def recent_files(self) -> list:
        """List of recently opened file paths."""
        return self.settings.value("recent_files", [], type=list)

    @recent_files.setter
    def recent_files(self, value: list):
        self.settings.setValue("recent_files", value)
        
    def add_recent_file(self, path: str):
        """Add a file to recent list, maintaining MRU order and max size."""
        current = self.recent_files
        # Normalize path
        path = path.replace("\\", "/")
        
        # Remove if exists (to move to top)
        if path in current:
            current.remove(path)
            
        # Insert at top
        current.insert(0, path)
        
        # Limit to 10
        if len(current) > 10:
            current = current[:10]
            
        self.recent_files = current
