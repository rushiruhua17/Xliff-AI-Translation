    def setup_translate_tab(self):
        layout = QVBoxLayout(self.tab_translate)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Top Bar: File Actions & Stats
        top_bar = QHBoxLayout()
        
        self.btn_open = QPushButton("📂 Open")
        self.btn_open.clicked.connect(self.open_file)
        top_bar.addWidget(self.btn_open)
        
        self.btn_save = QPushButton("💾 Export")
        self.btn_save.clicked.connect(self.save_file)
        top_bar.addWidget(self.btn_save)
        
        self.btn_trans = QPushButton("🚀 Translate All")
        self.btn_trans.clicked.connect(lambda: self.start_translation())
        top_bar.addWidget(self.btn_trans)
        
        top_bar.addSpacing(20)
        self.lbl_stats = QLabel("No file loaded")
        top_bar.addWidget(self.lbl_stats)
        
        top_bar.addStretch()
        
        # Theme Toggle (Small)
        self.btn_theme = QPushButton("🌓")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.clicked.connect(self.toggle_theme)
        top_bar.addWidget(self.btn_theme)
        
        layout.addLayout(top_bar)
        
        # Toolbar: Filter & Actions
        toolbar = QHBoxLayout()
        
        # Search
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search source/target...")
        self.txt_search.textChanged.connect(self.on_search_changed)
        toolbar.addWidget(self.txt_search, 1)
        
        # Filters
        self.btn_grp_filter = []
        for name in ["All", "Untranslated", "Translated", "Edited", "Locked"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            if name == "All": btn.setChecked(True)
            btn.clicked.connect(lambda checked, n=name: self.on_filter_btn_clicked(n))
            toolbar.addWidget(btn)
            self.btn_grp_filter.append(btn)
            
        layout.addLayout(toolbar)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Table
        self.table = QTableView()
        self.table.setModel(self.proxy_model) 
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        
        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Up"), self.table, lambda: self.navigate_grid(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self.table, lambda: self.navigate_grid(1))
        
        # Table Headers
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # State
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Tags (New)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # QA (New)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Source
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Target
        
        layout.addWidget(self.table)

    def setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # LLM Config Group
        grp_llm = QGroupBox("AI Configuration")
        form_layout = QVBoxLayout()
        
        # Provider
        h_prov = QHBoxLayout()
        h_prov.addWidget(QLabel("Provider:"))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["SiliconFlow", "OpenAI", "DeepSeek"])
        self.combo_provider.currentTextChanged.connect(self.on_provider_changed)
        h_prov.addWidget(self.combo_provider)
        form_layout.addLayout(h_prov)
        
        # API Key
        h_key = QHBoxLayout()
        h_key.addWidget(QLabel("API Key:"))
        self.txt_apikey = QLineEdit()
        self.txt_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_apikey.setPlaceholderText("sk-...")
        h_key.addWidget(self.txt_apikey)
        form_layout.addLayout(h_key)
        
        # Base URL
        h_url = QHBoxLayout()
        h_url.addWidget(QLabel("Base URL:"))
        self.txt_base_url = QLineEdit()
        self.txt_base_url.setPlaceholderText("https://api.openai.com/v1")
        h_url.addWidget(self.txt_base_url)
        form_layout.addLayout(h_url)
        
        # Model
        h_model = QHBoxLayout()
        h_model.addWidget(QLabel("Model:"))
        self.txt_model = QLineEdit()
        self.txt_model.setPlaceholderText("gpt-3.5-turbo")
        h_model.addWidget(self.txt_model)
        form_layout.addLayout(h_model)
        
        # Test Connection
        self.btn_test_conn = QPushButton("📡 Test Connection")
        self.btn_test_conn.clicked.connect(self.test_connection)
        form_layout.addWidget(self.btn_test_conn)

        grp_llm.setLayout(form_layout)
        layout.addWidget(grp_llm)
        
        # Language Config
        grp_lang = QGroupBox("Language Defaults")
        l_layout = QHBoxLayout()
        self.combo_src = QComboBox()
        self.combo_src.addItems(["zh-CN", "en", "ja", "de", "fr"])
        self.combo_tgt = QComboBox()
        self.combo_tgt.addItems(["en", "zh-CN", "ja", "de", "fr"])
        l_layout.addWidget(QLabel("Source:"))
        l_layout.addWidget(self.combo_src)
        l_layout.addWidget(QLabel("Target:"))
        l_layout.addWidget(self.combo_tgt)
        grp_lang.setLayout(l_layout)
        layout.addWidget(grp_lang)

        layout.addStretch()
