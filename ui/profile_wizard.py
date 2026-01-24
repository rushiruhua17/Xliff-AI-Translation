from enum import IntEnum
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QCheckBox, QTextEdit, QStackedWidget, QPushButton, 
    QMessageBox, QFormLayout, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt, QSettings
from core.profile import TranslationProfile, ProfileStatus, ProfileTemplate, TranslationProfileContainer
from ui.components import CollapsibleBox


class WizardResult(IntEnum):
    ACCEPTED = 1
    SKIPPED = 2
    CANCELLED = 0

class ProfileWizardDialog(QDialog):
    def __init__(self, profile: TranslationProfile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Setup Wizard")
        self.resize(600, 500)
        
        # Data
        self.profile = profile # Reference to the object we are editing
        self.result_code = WizardResult.CANCELLED
        self.settings = QSettings("Gemini", "XLIFF_AI_Assistant")
        self.is_dirty = False
        
        # Layout
        self.main_layout = QVBoxLayout(self)
        
        # Stack
        self.stack = QStackedWidget()
        self.step1 = self.create_step1_metadata()
        self.step2 = self.create_step2_brief()
        self.stack.addWidget(self.step1)
        self.stack.addWidget(self.step2)
        
        self.main_layout.addWidget(self.stack)
        
        # Buttons
        self.btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_skip = QPushButton("Skip Setup")
        self.btn_back = QPushButton("Back")
        self.btn_next = QPushButton("Next")
        
        self.btn_back.setVisible(False)
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_skip.clicked.connect(self.on_skip)
        self.btn_back.clicked.connect(self.on_back)
        self.btn_next.clicked.connect(self.on_next)
        
        self.btn_layout.addWidget(self.btn_cancel)
        self.btn_layout.addWidget(self.btn_skip)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.btn_back)
        self.btn_layout.addWidget(self.btn_next)
        
        self.main_layout.addLayout(self.btn_layout)
        
        # Apply Smart Defaults (Phase 4)
        self.apply_smart_defaults()
        
        # Connect change signals for dirty tracking
        self.connect_dirty_signals()

    def connect_dirty_signals(self):
        # Step 1
        self.inp_client.textChanged.connect(self.set_dirty)
        self.inp_domain.textChanged.connect(self.set_dirty)
        self.inp_audience.textChanged.connect(self.set_dirty)
        
        # Step 2
        self.combo_tone.currentTextChanged.connect(self.set_dirty)
        self.combo_formality.currentTextChanged.connect(self.set_dirty)
        self.inp_locale.textChanged.connect(self.set_dirty)
        self.txt_style.textChanged.connect(self.set_dirty)
        
        # Advanced
        self.combo_strictness.currentTextChanged.connect(self.set_dirty)
        self.chk_explanation.stateChanged.connect(self.set_dirty)
        self.inp_dnt.textChanged.connect(self.set_dirty)
        self.chk_nums.stateChanged.connect(self.set_dirty)
        self.combo_units.currentTextChanged.connect(self.set_dirty)
        self.chk_dual.stateChanged.connect(self.set_dirty)
        self.chk_placeholders.stateChanged.connect(self.set_dirty)

    def set_dirty(self):
        self.is_dirty = True

    def apply_smart_defaults(self):
        # Only apply if fields are empty (don't overwrite existing profile data)
        if not self.profile.project_metadata.client_name:
            self.inp_client.setText(self.settings.value("wizard_last_client", ""))
        
        if not self.profile.project_metadata.domain:
            self.inp_domain.setText(self.settings.value("wizard_last_domain", ""))
            
        if not self.profile.brief.tone or self.profile.brief.tone == "neutral":
             last_tone = self.settings.value("wizard_last_tone", "neutral")
             self.combo_tone.setCurrentText(last_tone)
             
        if not self.profile.brief.locale_variant:
            self.inp_locale.setText(self.settings.value("wizard_last_locale", ""))
            
        # Last Template (Prompt 4)
        last_template = self.settings.value("wizard_last_template_index", 0, type=int)
        self.combo_template.setCurrentIndex(last_template)

    def save_smart_defaults(self):
        # Save generic preferences for next time
        self.settings.setValue("wizard_last_client", self.inp_client.text())
        self.settings.setValue("wizard_last_domain", self.inp_domain.text())
        self.settings.setValue("wizard_last_tone", self.combo_tone.currentText())
        self.settings.setValue("wizard_last_locale", self.inp_locale.text())
        self.settings.setValue("wizard_last_template_index", self.combo_template.currentIndex())

    def create_step1_metadata(self):
        w = QWidget()
        layout = QFormLayout()
        
        self.inp_client = QLineEdit(self.profile.project_metadata.client_name)
        self.inp_client.setPlaceholderText("e.g. Acme Corp")
        
        self.inp_domain = QLineEdit(self.profile.project_metadata.domain)
        self.inp_domain.setPlaceholderText("e.g. Medical, Legal, Gaming")
        
        self.inp_audience = QLineEdit(self.profile.project_metadata.target_audience)
        self.inp_audience.setPlaceholderText("e.g. End Users, Developers")
        
        layout.addRow("Client Name:", self.inp_client)
        layout.addRow("Domain / Subject:", self.inp_domain)
        layout.addRow("Target Audience:", self.inp_audience)
        
        w.setLayout(layout)
        return w

    def create_step2_brief(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        # Template Selector (Phase 1)
        h_template = QHBoxLayout()
        h_template.addWidget(QLabel("Template:"))
        self.combo_template = QComboBox()
        self.combo_template.addItem("Custom / Manual", None)
        self.combo_template.addItem("User Manual (Neutral)", ProfileTemplate.MANUAL)
        self.combo_template.addItem("Warranty Policy (Formal)", ProfileTemplate.WARRANTY)
        self.combo_template.addItem("Training Course (Friendly)", ProfileTemplate.TRAINING)
        
        self.combo_template.currentIndexChanged.connect(self.on_template_changed)
        h_template.addWidget(self.combo_template)
        
        # Auto-Detect Button (Phase 2)
        self.btn_auto = QPushButton("✨ Auto-Detect")
        self.btn_auto.setToolTip("Use AI to analyze source text and suggest profile settings")
        self.btn_auto.clicked.connect(self.on_auto_detect)
        h_template.addWidget(self.btn_auto)
        
        layout.addLayout(h_template)
        layout.addSpacing(10)
        
        # Brief Fields
        form = QFormLayout()
        self.combo_tone = QComboBox()
        self.combo_tone.addItems(["neutral", "formal", "casual", "friendly", "authoritative", "neutral_informative", "formal_legal", "friendly_instructive", "marketing"])
        self.combo_tone.setCurrentText(self.profile.brief.tone)
        
        self.combo_formality = QComboBox()
        self.combo_formality.addItems(["neutral", "formal", "informal", "neutral_professional", "casual"])
        self.combo_formality.setCurrentText(self.profile.brief.formality)
        
        self.inp_locale = QLineEdit(self.profile.brief.locale_variant)
        self.inp_locale.setPlaceholderText("e.g. zh-CN, en-US")
        
        form.addRow("Tone:", self.combo_tone)
        form.addRow("Formality:", self.combo_formality)
        form.addRow("Locale Variant:", self.inp_locale)
        
        layout.addLayout(form)
        
        # Advanced (Collapsible)
        self.adv_box = CollapsibleBox("Advanced Settings")
        adv_layout = QVBoxLayout()
        
        # 1. Terminology Policy
        term_group = QGroupBox("Terminology Policy")
        term_layout = QFormLayout()
        self.combo_strictness = QComboBox()
        self.combo_strictness.addItems(["strict", "prefer", "loose"])
        self.combo_strictness.setCurrentText(self.profile.brief.terminology.strictness)
        
        self.chk_explanation = QCheckBox("Allow Explanations (in brackets)")
        self.chk_explanation.setChecked(self.profile.brief.terminology.allow_explanation)
        
        self.inp_dnt = QLineEdit(", ".join(self.profile.brief.terminology.do_not_translate))
        self.inp_dnt.setPlaceholderText("Comma separated list of terms")
        
        term_layout.addRow("Strictness:", self.combo_strictness)
        term_layout.addRow("", self.chk_explanation)
        term_layout.addRow("Do Not Translate:", self.inp_dnt)
        term_group.setLayout(term_layout)
        adv_layout.addWidget(term_group)
        
        # 2. Formatting Rules
        fmt_group = QGroupBox("Formatting & Units")
        fmt_layout = QFormLayout()
        
        self.chk_nums = QCheckBox("Preserve Source Numbers")
        self.chk_nums.setChecked(self.profile.brief.formatting.preserve_source_numbers)
        
        self.combo_units = QComboBox()
        self.combo_units.addItems(["SI", "Imperial", "Mixed"])
        self.combo_units.setCurrentText(self.profile.brief.formatting.unit_system)
        
        self.chk_dual = QCheckBox("Show Dual Units (e.g. SI + Imperial)")
        self.chk_dual.setChecked(self.profile.brief.formatting.dual_units)
        
        self.chk_placeholders = QCheckBox("Strict Placeholders {n}")
        self.chk_placeholders.setChecked(self.profile.brief.formatting.preserve_placeholders)
        
        fmt_layout.addRow("", self.chk_nums)
        fmt_layout.addRow("Unit System:", self.combo_units)
        fmt_layout.addRow("", self.chk_dual)
        fmt_layout.addRow("", self.chk_placeholders)
        fmt_group.setLayout(fmt_layout)
        adv_layout.addWidget(fmt_group)
        
        # 3. Style Guide Notes
        self.txt_style = QTextEdit()
        self.txt_style.setPlaceholderText("Paste style guide notes here...")
        self.txt_style.setText(self.profile.brief.style_guide_notes)
        self.txt_style.setMaximumHeight(100)
        adv_layout.addWidget(QLabel("Additional Style Notes:"))
        adv_layout.addWidget(self.txt_style)
        
        self.adv_box.set_content_layout(adv_layout)
        layout.addWidget(self.adv_box)
        
        w.setLayout(layout)
        return w

    def on_template_changed(self, index):
        data = self.combo_template.currentData()
        if data:
            # Apply template
            template_profile = TranslationProfileContainer.get_template(data)
            
            # Update UI fields
            self.combo_tone.setCurrentText(template_profile.brief.tone)
            self.combo_formality.setCurrentText(template_profile.brief.formality)
            self.txt_style.setText(template_profile.brief.style_guide_notes)
            
            # Update Advanced fields
            self.combo_strictness.setCurrentText(template_profile.brief.terminology.strictness)
            self.chk_explanation.setChecked(template_profile.brief.terminology.allow_explanation)
            self.chk_nums.setChecked(template_profile.brief.formatting.preserve_source_numbers)
            self.combo_units.setCurrentText(template_profile.brief.formatting.unit_system)
            
            self.set_dirty()

    def on_auto_detect(self):
        # We need sample text. In a real app, this should be passed in.
        # For now, let's signal that we need auto-detection, or if we have parent window access...
        # A cleaner way is to emit a signal, but for MVP let's assume parent is MainWindow
        # and has access to 'units'.
        
        # But wait, Dialog is modal. We can't easily access the worker if it's not passed.
        # Let's show a placeholder or try to find the main window reference.
        
        parent = self.parent()
        if not parent or not hasattr(parent, 'get_client') or not hasattr(parent, 'units'):
            QMessageBox.warning(self, "Unavailable", "Auto-detect is not available in this context.")
            return
            
        units = parent.units
        if not units:
            QMessageBox.warning(self, "No Data", "No source text available for analysis.")
            return
            
        # Prepare sample text (first 2000 chars from first few units)
        sample_text = ""
        for u in units[:10]:
            sample_text += u.source_abstracted + "\n"
            if len(sample_text) > 2000: break
            
        try:
            client_config = parent.get_client_config()
        except Exception as e:
            QMessageBox.warning(self, "Config Error", str(e))
            return
            
        # Import here to avoid circular dependency at module level if any
        from core.workers import ProfileGeneratorWorker
        
        self.btn_auto.setEnabled(False)
        self.btn_auto.setText("Analyzing...")
        
        self.gen_worker = ProfileGeneratorWorker(sample_text, client_config)
        self.gen_worker.finished.connect(self.on_auto_detect_finished)
        self.gen_worker.error.connect(lambda e: (
            self.btn_auto.setEnabled(True),
            self.btn_auto.setText("✨ Auto-Detect"),
            QMessageBox.critical(self, "Analysis Failed", e)
        ))
        self.gen_worker.start()

    def on_auto_detect_finished(self, suggested_profile):
        self.btn_auto.setEnabled(True)
        self.btn_auto.setText("✨ Auto-Detect")
        
        # Apply suggestions
        if suggested_profile.project_metadata.project_type:
            self.inp_domain.setText(suggested_profile.project_metadata.project_type)
        
        if suggested_profile.project_metadata.target_audience:
            self.inp_audience.setText(suggested_profile.project_metadata.target_audience)
            
        if suggested_profile.brief.tone:
            # Map loosely or set custom? 
            # Combo box might not have exact match, try set current text or add it
            idx = self.combo_tone.findText(suggested_profile.brief.tone, Qt.MatchFlag.MatchContains)
            if idx >= 0:
                self.combo_tone.setCurrentIndex(idx)
            else:
                # Add temporary item? Or just ignore if strict. 
                # Let's try to map to closest or just force text if editable (it is not editable by default)
                pass 
        
        if suggested_profile.brief.formality:
            idx = self.combo_formality.findText(suggested_profile.brief.formality, Qt.MatchFlag.MatchContains)
            if idx >= 0: self.combo_formality.setCurrentIndex(idx)
            
        if suggested_profile.brief.style_guide_notes:
            self.txt_style.setText(suggested_profile.brief.style_guide_notes)
            
        # Advanced fields from AI
        if suggested_profile.brief.terminology.strictness:
            self.combo_strictness.setCurrentText(suggested_profile.brief.terminology.strictness)
            
        if suggested_profile.brief.terminology.do_not_translate:
            self.inp_dnt.setText(", ".join(suggested_profile.brief.terminology.do_not_translate))
            
        if suggested_profile.brief.formatting.unit_system:
            self.combo_units.setCurrentText(suggested_profile.brief.formatting.unit_system)
            
        QMessageBox.information(self, "Analysis Complete", "Profile settings have been updated based on AI analysis.")
        self.set_dirty()

    def save_data_to_profile(self):
        # Step 1
        self.profile.project_metadata.client_name = self.inp_client.text()
        self.profile.project_metadata.domain = self.inp_domain.text()
        self.profile.project_metadata.target_audience = self.inp_audience.text()
        
        # Step 2
        self.profile.brief.tone = self.combo_tone.currentText()
        self.profile.brief.formality = self.combo_formality.currentText()
        self.profile.brief.locale_variant = self.inp_locale.text()
        self.profile.brief.style_guide_notes = self.txt_style.toPlainText()
        
        # Advanced - Terminology
        self.profile.brief.terminology.strictness = self.combo_strictness.currentText()
        self.profile.brief.terminology.allow_explanation = self.chk_explanation.isChecked()
        dnt_text = self.inp_dnt.text().strip()
        self.profile.brief.terminology.do_not_translate = [t.strip() for t in dnt_text.split(",") if t.strip()]
        
        # Advanced - Formatting
        self.profile.brief.formatting.preserve_source_numbers = self.chk_nums.isChecked()
        self.profile.brief.formatting.unit_system = self.combo_units.currentText()
        self.profile.brief.formatting.dual_units = self.chk_dual.isChecked()
        self.profile.brief.formatting.preserve_placeholders = self.chk_placeholders.isChecked()

    def reject(self):
        # Dirty check (Phase 7)
        if self.is_dirty:
            reply = QMessageBox.question(
                self, "Discard Changes?", 
                "You have unsaved changes. Are you sure you want to close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        super().reject()

    def on_next(self):
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
            self.btn_back.setVisible(True)
            self.btn_next.setText("Finish")
        else:
            # Finish
            self.save_data_to_profile()
            self.save_smart_defaults() # Save for next time
            self.result_code = WizardResult.ACCEPTED
            self.accept()

    def on_back(self):
        self.stack.setCurrentIndex(0)
        self.btn_back.setVisible(False)
        self.btn_next.setText("Next")

    def on_skip(self):
        self.result_code = WizardResult.SKIPPED
        # Skip doesn't need dirty check as it's an explicit action to ignore setup
        super().reject() 

    def get_profile(self):
        return self.profile
