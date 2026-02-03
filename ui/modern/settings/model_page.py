from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QStackedWidget, QLabel, QFrame, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from qfluentwidgets import (CardWidget, StrongBodyLabel, BodyLabel, LineEdit, 
                            PrimaryPushButton, PushButton, ComboBox, SwitchButton,
                            FluentIcon, SubtitleLabel, ListWidget, ToolButton, 
                            HyperlinkButton, InfoBar, InfoBarPosition)
import requests
import uuid

# Provider Metadata Repository
PROVIDER_DATA = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "help_url": "https://platform.openai.com/api-keys",
        "default_models": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        "icon": FluentIcon.GLOBE
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "help_url": "https://platform.deepseek.com/api_keys",
        "default_models": ["deepseek-chat", "deepseek-reasoner"],
        "icon": FluentIcon.CHAT
    },
    "Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "help_url": "https://aistudio.google.com/app/apikey",
        "default_models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"],
        "icon": FluentIcon.IOT
    },
    "Ollama": {
        "base_url": "http://localhost:11434/v1",
        "help_url": "https://ollama.com",
        "default_models": ["llama3", "mistral", "qwen2"],
        "icon": FluentIcon.COMMAND_PROMPT
    },
    "Azure": {
        "base_url": "", # User must fill
        "help_url": "https://portal.azure.com",
        "default_models": ["gpt-4"],
        "icon": FluentIcon.CLOUD
    },
    "Custom": {
        "base_url": "",
        "help_url": "",
        "default_models": [],
        "icon": FluentIcon.EDIT
    }
}

def collect_task_mappings(task_combos: dict) -> dict:
    new_mappings = {}
    for task, combo in (task_combos or {}).items():
        if hasattr(combo, "count") and combo.count() <= 0:
            raise ValueError(
                f"Task '{task}' has no available models. Please enable a provider and add models first.\n"
                f"任务“{task}”没有可选模型，请先启用 Provider 并添加模型。"
            )

        data = combo.currentData() if hasattr(combo, "currentData") else None
        if not data and hasattr(combo, "currentIndex") and hasattr(combo, "setCurrentIndex") and hasattr(combo, "itemData"):
            idx = combo.currentIndex()
            if idx is None or idx < 0:
                combo.setCurrentIndex(0)
                idx = 0
            data = combo.itemData(idx)

        if not data and hasattr(combo, "currentText"):
            text = combo.currentText() or ""
            if " - " in text:
                provider, model = text.split(" - ", 1)
                provider = provider.strip()
                model = model.strip()
                if provider and model:
                    data = f"{provider}_{model}"

        if not data:
            raise ValueError(
                f"No default model selected for task: {task}. Please select one and save.\n"
                f"任务“{task}”未选择默认模型，请先选择并保存。"
            )

        new_mappings[task] = data

    return new_mappings

class ModelSettingsPage(QWidget):
    """
    Cherry Studio Style Model Configuration Page.
    """
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.ui_map = {} # Store UI references for each provider: {provider: {api_key, base_url, model_list, enable}}
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Left Sidebar ---
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar.setStyleSheet("QListWidget { background-color: transparent; border-right: 1px solid #E5E5E5; }")
        self.sidebar.currentRowChanged.connect(self.on_sidebar_changed)
        
        # Default Models Item
        item_defaults = QListWidgetItem("Default Models")
        item_defaults.setIcon(FluentIcon.ROBOT.icon())
        self.sidebar.addItem(item_defaults)
        
        # Providers Items
        self.providers = list(PROVIDER_DATA.keys())
        for p in self.providers:
            item = QListWidgetItem(p)
            icon = PROVIDER_DATA[p]["icon"]
            item.setIcon(icon.icon()) 
            self.sidebar.addItem(item)
            
        layout.addWidget(self.sidebar)
        
        # --- Right Content ---
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)
        
        # 1. Defaults Page
        self.page_defaults = self.create_defaults_page()
        self.content_stack.addWidget(self.page_defaults)
        
        # 2. Provider Pages
        for p in self.providers:
            page = self.create_provider_page(p)
            self.content_stack.addWidget(page)
            
        # Select first
        self.sidebar.setCurrentRow(0)

    def create_defaults_page(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        layout.addWidget(SubtitleLabel("Default Models by Task", w))
        layout.addWidget(BodyLabel("Assign specific models to different tasks for optimal cost/performance.", w))
        lbl_save_hint = BodyLabel("Changes take effect after clicking Save. 修改后请点击保存才会生效。", w)
        lbl_save_hint.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(lbl_save_hint)
        layout.addSpacing(10)
        
        self.task_combos = {}
        
        tasks = [
            ("translation", "Translation", "Main translation task. Choose your most capable model.", "GPT-4o / Claude 3.5"),
            ("repair", "Auto-Repair", "Fixes tag errors and format issues. Fast models preferred.", "Gemini Flash / GPT-4o-mini"),
            ("profile_analysis", "Profile Detection", "Analyzes text style and audience. Fast models preferred.", "Gemini Flash")
        ]
        
        for task_key, task_name, desc, hint in tasks:
            card = CardWidget(w)
            c_layout = QVBoxLayout(card)
            
            header = QHBoxLayout()
            header.addWidget(StrongBodyLabel(task_name, card))
            header.addStretch()
            
            combo = ComboBox()
            combo.setMinimumWidth(250)
            self.task_combos[task_key] = combo
            header.addWidget(combo)
            
            c_layout.addLayout(header)
            c_layout.addWidget(BodyLabel(desc, card))
            lbl_hint = BodyLabel(f"Recommended: {hint}", card)
            lbl_hint.setStyleSheet("color: gray; font-size: 12px;")
            c_layout.addWidget(lbl_hint)
            
            layout.addWidget(card)
            
        layout.addStretch()
        return w

    def create_provider_page(self, provider_name):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        data = PROVIDER_DATA.get(provider_name, {})
        
        # Header
        h_layout = QHBoxLayout()
        h_layout.addWidget(SubtitleLabel(provider_name, w))
        
        # External Link Button
        if data.get("help_url"):
            btn_link = ToolButton(FluentIcon.LINK, w)
            btn_link.setToolTip(f"Open {provider_name} Dashboard")
            btn_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(data["help_url"])))
            h_layout.addWidget(btn_link)
            
        h_layout.addStretch()
        switch = SwitchButton("Enable")
        switch.setChecked(False) # Default disabled
        for signal_name in ("checkedChanged", "toggled"):
            if hasattr(switch, signal_name):
                getattr(switch, signal_name).connect(lambda *_: self.refresh_default_combos())
                break
        h_layout.addWidget(switch)
        layout.addLayout(h_layout)
        
        # API Key Section
        layout.addWidget(StrongBodyLabel("API Key", w))
        
        key_layout = QHBoxLayout()
        api_key = LineEdit()
        api_key.setEchoMode(LineEdit.EchoMode.Password)
        api_key.setPlaceholderText(f"sk-...")
        key_layout.addWidget(api_key)
        
        # Test Connection Button (Check Icon)
        btn_test = ToolButton(FluentIcon.ACCEPT, w)
        btn_test.setToolTip("Test Connection")
        # Need to capture current variables
        btn_test.clicked.connect(lambda _, p=provider_name, k=api_key, u=None: self.test_connection_wrapper(p, k))
        key_layout.addWidget(btn_test)
        
        layout.addLayout(key_layout)
        
        # "Get API Key" Link
        if data.get("help_url"):
            link_layout = QHBoxLayout()
            link_btn = HyperlinkButton(data["help_url"], "Get API Key", w)
            link_btn.setIcon(FluentIcon.LINK)
            link_layout.addWidget(link_btn)
            link_layout.addStretch()
            layout.addLayout(link_layout)
        
        # Base URL Section
        layout.addWidget(StrongBodyLabel("API Base URL", w))
        base_url = LineEdit()
        base_url.setPlaceholderText("https://...")
        base_url.setText(data.get("base_url", ""))
        layout.addWidget(base_url)
        lbl_tip = BodyLabel("Leave unchanged for official endpoints.", w)
        lbl_tip.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(lbl_tip)
        
        # Update test button to use base_url
        # We use a wrapper to access the latest text
        
        layout.addSpacing(10)
        
        # Model List Manager
        layout.addWidget(StrongBodyLabel("Available Models", w))
        model_list = QListWidget()
        model_list.setFixedHeight(150)
        model_list.setAlternatingRowColors(True)
        model_list.addItems(data.get("default_models", []))
            
        layout.addWidget(model_list)
        
        # Add/Remove Buttons
        btn_row = QHBoxLayout()
        btn_add = PushButton("Add Model")
        btn_add.clicked.connect(lambda _, l=model_list: self.add_model_to_list(l))
        
        btn_del = PushButton("Remove")
        btn_del.clicked.connect(lambda _, l=model_list: self.remove_model_from_list(l))
        
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # Store references for saving/loading
        self.ui_map[provider_name] = {
            "enable": switch,
            "api_key": api_key,
            "base_url": base_url,
            "model_list": model_list
        }
        
        layout.addStretch()
        return w

    def add_model_to_list(self, list_widget):
        text, ok = QInputDialog.getText(self, "Add Model", "Model ID (e.g. gpt-4o):")
        if ok and text:
            list_widget.addItem(text)
            self.refresh_default_combos()

    def remove_model_from_list(self, list_widget):
        row = list_widget.currentRow()
        if row >= 0:
            list_widget.takeItem(row)
            self.refresh_default_combos()

    def on_sidebar_changed(self, row):
        self.content_stack.setCurrentIndex(row)
        # If switching to Defaults page (row 0), refresh combos
        if row == 0:
            self.refresh_default_combos()

    def test_connection_wrapper(self, provider_name, api_key_widget):
        # Helper to get current text values
        key = api_key_widget.text()
        base_url = self.ui_map[provider_name]["base_url"].text()
        self.test_connection(provider_name, key, base_url)

    def test_connection(self, provider, key, url):
        """Test the connection to the LLM provider"""
        if not key:
            InfoBar.warning("Missing Key", "Please enter an API Key first.", parent=self)
            return
            
        # Normalize URL
        if not url.endswith("/"): url += "/"
        
        # Generic OpenAI-compatible check
        target_url = f"{url}models"
        headers = {"Authorization": f"Bearer {key}"}
        
        try:
            # Set timeout to avoid freezing UI for too long
            response = requests.get(target_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                InfoBar.success("Connected", f"Successfully connected to {provider}!", parent=self)
            elif response.status_code == 401:
                InfoBar.error("Authentication Failed", "Invalid API Key.", parent=self)
            else:
                InfoBar.error("Connection Error", f"Server returned {response.status_code}: {response.text[:50]}", parent=self)
                
        except Exception as e:
            InfoBar.error("Network Error", str(e), parent=self)

    def load_settings(self):
        """Load settings from AppConfig into UI"""
        profiles = self.config.model_profiles
        mappings = self.config.task_mappings
        
        # 1. Populate Providers
        # We group profiles by provider to fill the UI
        # Since our UI assumes one API Key per provider, we take the first matching profile
        
        provider_data = {} # provider -> {api_key, base_url, models: set()}
        
        for p in profiles:
            prov = p.get("provider", "Custom")
            # Map "custom" to "Custom" if needed, case insensitive
            prov_key = next((k for k in self.providers if k.lower() == prov.lower()), "Custom")
            
            if prov_key not in provider_data:
                provider_data[prov_key] = {
                    "api_key": p.get("api_key", ""),
                    "base_url": p.get("base_url", ""),
                    "models": set()
                }
            
            # Add model
            if p.get("model"):
                provider_data[prov_key]["models"].add(p.get("model"))

        # Fill UI
        for p_name, data in provider_data.items():
            if p_name in self.ui_map:
                ui = self.ui_map[p_name]
                ui["enable"].setChecked(True) # If profile exists, enable it
                ui["api_key"].setText(data["api_key"])
                if data["base_url"]:
                    ui["base_url"].setText(data["base_url"])
                
                # Merge default models with saved models
                # We clear defaults if we have saved models? Or append?
                # Let's keep defaults + saved to ensure list isn't empty
                # But to avoid duplicates, we rebuild list
                
                current_items = [ui["model_list"].item(i).text() for i in range(ui["model_list"].count())]
                existing_set = set(current_items)
                
                for m in data["models"]:
                    if m not in existing_set:
                        ui["model_list"].addItem(m)

        # 2. Populate Task Combos
        # We need to populate them first
        self.refresh_default_combos()
        
        # Set selections
        for task, combo in self.task_combos.items():
            profile_id = mappings.get(task)
            if profile_id:
                # Find index
                idx = combo.findData(profile_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def refresh_default_combos(self):
        """Re-populate all task combos based on enabled providers and their models"""
        
        # 1. Collect all available models
        available_options = [] # (Name, Data)
        
        for p_name, ui in self.ui_map.items():
            if not ui["enable"].isChecked():
                continue
                
            # Get models from list
            count = ui["model_list"].count()
            for i in range(count):
                model_name = ui["model_list"].item(i).text()
                display_name = f"{p_name} - {model_name}"
                # Generate a deterministic ID for saving
                profile_id = f"{p_name}_{model_name}"
                available_options.append((display_name, profile_id))
        
        # 2. Update Combos
        for combo in self.task_combos.values():
            current_id = combo.currentData()
            combo.clear()
            
            for text, data in available_options:
                combo.addItem(text, data)
                
            # Restore selection if possible
            if current_id:
                idx = combo.findData(current_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def save_settings(self):
        """Collect data and save to AppConfig"""
        self.refresh_default_combos()
        new_profiles = []
        
        # 1. Generate Profiles from UI state
        for p_name, ui in self.ui_map.items():
            if not ui["enable"].isChecked():
                continue
                
            api_key = ui["api_key"].text()
            base_url = ui["base_url"].text()
            
            # Create a profile for EACH model in the list
            count = ui["model_list"].count()
            for i in range(count):
                model_name = ui["model_list"].item(i).text()
                profile_id = f"{p_name}_{model_name}"
                
                new_profiles.append({
                    "id": profile_id,
                    "name": f"{p_name} - {model_name}",
                    "provider": p_name.lower(), # Config expects lowercase probably
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": model_name
                })
        
        # 2. Save Profiles
        self.config.model_profiles = new_profiles
        
        # 3. Save Mappings
        new_mappings = collect_task_mappings(self.task_combos)
            
        self.config.task_mappings = new_mappings
        
        # 4. Force Sync to Disk
        self.config.sync()
        
        InfoBar.success("Settings Saved", "Model configurations have been updated.", parent=self)
