from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGroupBox, QFormLayout
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import (CardWidget, StrongBodyLabel, BodyLabel, ComboBox, 
                            LineEdit, TextEdit, PrimaryPushButton, PushButton, 
                            FluentIcon as FIF, ToolTipFilter, ToolTipPosition,
                            SwitchButton, CheckBox, ToolButton)

from core.profile import TranslationProfile, TranslationBrief

class ProfileConfigCard(CardWidget):
    """
    Widget for configuring Translation Profile (Tone, Audience, etc.)
    Used in ProjectInterface (Step 3) and EditorInterface (Dialog).
    """
    profile_saved = pyqtSignal(object) # Emits TranslationProfile
    request_auto_detect = pyqtSignal() # New signal for AI detection
    
    def __init__(self, parent=None, title="Edit Profile (Translation Style)"):
        super().__init__(parent)
        self.header_title = title
        self.profile = TranslationProfile()
        self.init_ui()
        
    def init_ui(self):
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(20, 20, 20, 20)
        self.v_layout.setSpacing(15)
        
        # Header
        h_header = QHBoxLayout()
        h_header.addWidget(StrongBodyLabel(self.header_title, self))
        h_header.addStretch()
        
        self.btn_auto = PushButton("✨ Auto-Detect", self)
        self.btn_auto.setToolTip("Let AI analyze the file to suggest settings")
        self.btn_auto.clicked.connect(self.auto_detect)
        h_header.addWidget(self.btn_auto)
        
        self.v_layout.addLayout(h_header)
        
        # Grid Layout for Fields
        # Row 1: Tone & Formality
        r1 = QHBoxLayout()
        
        # Tone
        v_tone = QVBoxLayout()
        v_tone.addWidget(BodyLabel("Tone", self))
        self.combo_tone = ComboBox(self)
        self.combo_tone.addItems(["Neutral", "Formal", "Casual", "Friendly", "Authoritative", "Marketing"])
        v_tone.addWidget(self.combo_tone)
        r1.addLayout(v_tone)
        
        # Formality
        v_formality = QVBoxLayout()
        v_formality.addWidget(BodyLabel("Formality", self))
        self.combo_formality = ComboBox(self)
        self.combo_formality.addItems(["Neutral", "Formal", "Informal"])
        v_formality.addWidget(self.combo_formality)
        r1.addLayout(v_formality)
        
        self.v_layout.addLayout(r1)
        
        # Row 2: Target Audience
        v_audience = QVBoxLayout()
        v_audience.addWidget(BodyLabel("Target Audience", self))
        self.txt_audience = LineEdit(self)
        self.txt_audience.setPlaceholderText("e.g. End Users, Developers, Legal Professionals")
        v_audience.addWidget(self.txt_audience)
        self.v_layout.addLayout(v_audience)
        
        # Row 3: Style Guide / Instructions
        v_style = QVBoxLayout()
        v_style.addWidget(BodyLabel("Style Guide / Additional Instructions", self))
        self.txt_style = TextEdit(self)
        self.txt_style.setPlaceholderText("Enter specific instructions, do's and don'ts...")
        self.txt_style.setFixedHeight(80)
        v_style.addWidget(self.txt_style)
        self.v_layout.addLayout(v_style)
        
        # Footer Actions
        h_footer = QHBoxLayout()
        h_footer.addStretch()
        
        self.btn_save = PrimaryPushButton("Save Profile", self)
        self.btn_save.clicked.connect(self.save_profile)
        self.btn_save.setFixedWidth(120)
        h_footer.addWidget(self.btn_save)
        
        self.v_layout.addLayout(h_footer)
        
        self.init_advanced_settings()

    def init_advanced_settings(self):
        # Custom Collapsible Section
        self.adv_container = QWidget()
        adv_layout = QVBoxLayout(self.adv_container)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(5)
        
        # Header Row (Clickable)
        h_adv = QHBoxLayout()
        self.btn_expand = ToolButton(FIF.CHEVRON_RIGHT, self)
        self.btn_expand.clicked.connect(self.toggle_advanced)
        h_adv.addWidget(self.btn_expand)
        
        lbl_adv = StrongBodyLabel("Advanced Settings (Terminology & Formatting)", self)
        h_adv.addWidget(lbl_adv)
        h_adv.addStretch()
        adv_layout.addLayout(h_adv)
        
        # Content Area (Hidden by default)
        self.adv_content = QFrame()
        self.adv_content.setVisible(False)
        self.content_layout = QVBoxLayout(self.adv_content)
        self.content_layout.setContentsMargins(20, 0, 0, 0) # Indent
        
        # 1. Terminology Policy
        self.combo_strictness = ComboBox()
        self.combo_strictness.addItems(["strict", "prefer", "loose"])
        self._add_setting_row("Terminology Strictness:", self.combo_strictness)
        
        self.chk_explanation = CheckBox("Allow Explanations (in brackets)")
        self.content_layout.addWidget(self.chk_explanation)
        
        self.inp_dnt = LineEdit()
        self.inp_dnt.setPlaceholderText("Do Not Translate (comma separated)")
        self.content_layout.addWidget(self.inp_dnt)
        
        self.content_layout.addSpacing(10)
        
        # 2. Formatting
        self.chk_nums = CheckBox("Preserve Source Numbers")
        self.chk_nums.setChecked(True)
        self.content_layout.addWidget(self.chk_nums)
        
        self.combo_units = ComboBox()
        self.combo_units.addItems(["SI", "Imperial", "Mixed"])
        self._add_setting_row("Unit System:", self.combo_units)
        
        self.chk_dual = CheckBox("Show Dual Units")
        self.content_layout.addWidget(self.chk_dual)
        
        adv_layout.addWidget(self.adv_content)
        self.v_layout.addWidget(self.adv_container)

    def toggle_advanced(self):
        is_visible = self.adv_content.isVisible()
        self.adv_content.setVisible(not is_visible)
        # Fix icon name error: CARE_DOWN_SOLID_8 -> CARE_DOWN_SOLID or CHEVRON_DOWN
        self.btn_expand.setIcon(FIF.CARE_DOWN_SOLID if not is_visible else FIF.CHEVRON_RIGHT)

    def _add_setting_row(self, label_text, widget):
        h = QHBoxLayout()
        h.addWidget(BodyLabel(label_text))
        h.addWidget(widget)
        h.addStretch()
        self.content_layout.addLayout(h)
        
    def load_profile(self, profile: TranslationProfile):
        """Populate fields from existing profile"""
        self.profile = profile
        if not profile or not profile.brief:
            return
            
        brief = profile.brief
        
        # Set Tone
        self._set_combo_text(self.combo_tone, self._normalize_tone(brief.tone))
        
        # Set Formality
        self._set_combo_text(self.combo_formality, self._normalize_formality(brief.formality))
        
        # Set Audience
        self.txt_audience.setText(brief.target_audience)
        
        # Set Style
        self.txt_style.setText(brief.style_guide_notes)

        # Advanced Fields
        if hasattr(brief, "terminology") and brief.terminology:
            self._set_combo_text(self.combo_strictness, brief.terminology.strictness)
            self.chk_explanation.setChecked(bool(getattr(brief.terminology, "allow_explanation", False)))
            dnt_list = getattr(brief.terminology, "do_not_translate", []) or []
            self.inp_dnt.setText(", ".join(dnt_list))

        if hasattr(brief, "formatting") and brief.formatting:
            self.chk_nums.setChecked(bool(getattr(brief.formatting, "preserve_source_numbers", True)))
            self._set_combo_text(self.combo_units, getattr(brief.formatting, "unit_system", "SI"))
            self.chk_dual.setChecked(bool(getattr(brief.formatting, "dual_units", False)))

    def _normalize_tone(self, tone: str) -> str:
        if not tone:
            return ""
        mapping = {
            "neutral": "Neutral",
            "formal": "Formal",
            "casual": "Casual",
            "friendly": "Friendly",
            "authoritative": "Authoritative",
            "marketing": "Marketing",
            "professional": "Formal",
        }
        key = str(tone).strip().lower()
        return mapping.get(key, str(tone).strip().title())

    def _normalize_formality(self, formality: str) -> str:
        if not formality:
            return ""
        mapping = {
            "neutral": "Neutral",
            "formal": "Formal",
            "informal": "Informal",
        }
        key = str(formality).strip().lower()
        return mapping.get(key, str(formality).strip().title())
        
    def _set_combo_text(self, combo, text):
        # Workaround for ComboBox findText issue in qfluentwidgets wrapper
        # Iterate manually
        if not text:
            return
        
        for i in range(combo.count()):
            if combo.itemText(i).strip().lower() == str(text).strip().lower():
                combo.setCurrentIndex(i)
                return
        
        # If not found, add it? Or ignore.
        # Original logic:
        if not text:
            combo.setCurrentIndex(0)
        else:
            combo.setCurrentIndex(0)

    def get_current_profile(self):
        """Public method to get the current configured profile"""
        # Ensure latest values are captured
        self.save_profile() # This updates self.profile from UI
        return self.profile

    def save_profile(self):
        """Collect data and emit"""
        # Update internal profile object
        self.profile.brief.tone = self.combo_tone.currentText()
        self.profile.brief.formality = self.combo_formality.currentText()
        self.profile.brief.target_audience = self.txt_audience.text()
        self.profile.brief.style_guide_notes = self.txt_style.toPlainText()

        # Advanced Fields
        self.profile.brief.terminology.strictness = self.combo_strictness.currentText()
        self.profile.brief.terminology.allow_explanation = self.chk_explanation.isChecked()
        dnt_text = self.inp_dnt.text().strip()
        self.profile.brief.terminology.do_not_translate = [t.strip() for t in dnt_text.split(",") if t.strip()]
        
        self.profile.brief.formatting.preserve_source_numbers = self.chk_nums.isChecked()
        self.profile.brief.formatting.unit_system = self.combo_units.currentText()
        self.profile.brief.formatting.dual_units = self.chk_dual.isChecked()
        
        # Emit
        self.profile_saved.emit(self.profile)
        
        # Visual feedback
        self.btn_save.setText("Saved!")
        self.btn_save.setIcon(FIF.ACCEPT)
        # Reset after 2s (optional, but good UX)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._reset_save_btn())
        
    def _reset_save_btn(self):
        self.btn_save.setText("Save Profile")
        self.btn_save.setIcon(None)

    def auto_detect(self):
        """Emit signal to request AI analysis"""
        self.btn_auto.setText("Analyzing...")
        self.btn_auto.setEnabled(False)
        self.request_auto_detect.emit()
        
    def on_auto_detect_finished(self):
        """Reset button state"""
        self.btn_auto.setText("Detected!")
        self.btn_auto.setEnabled(True)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_auto.setText("✨ Auto-Detect"))
