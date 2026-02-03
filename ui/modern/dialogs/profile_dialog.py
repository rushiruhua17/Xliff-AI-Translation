from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from qfluentwidgets import MessageBoxBase, SubtitleLabel, PrimaryPushButton, PushButton

from ui.modern.widgets.profile_config_card import ProfileConfigCard
from core.profile import TranslationProfile

class ProfileConfigDialog(MessageBoxBase):
    """
    Dialog wrapping ProfileConfigCard
    """
    def __init__(self, parent=None, profile: TranslationProfile = None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("Configure Translation Profile", self)
        
        self.viewLayout.addWidget(self.titleLabel)
        
        self.profile_card = ProfileConfigCard(self, title="Translation Profile Settings")
        
        if profile:
            self.profile_card.load_profile(profile)
            
        self.viewLayout.addWidget(self.profile_card)
        
        # Adjust layout
        self.widget.setMinimumWidth(500)
        
        # Hide the default Yes/No buttons of MessageBoxBase if we want to rely on Card's Save
        # Or we can wire the Card's Save to the Dialog's Accept.
        # Let's hide the default buttons and use the Card's "Save" to close.
        self.yesButton.hide()
        self.cancelButton.setText("Cancel")
        
        # Wire card save to close
        self.profile_card.profile_saved.connect(self.on_save)
        
    def on_save(self, profile):
        self.profile = profile
        self.accept()
