from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt
from qfluentwidgets import (SingleDirectionScrollArea, SubtitleLabel, BodyLabel, 
                            CardWidget, StrongBodyLabel, PushButton, FluentIcon as FIF,
                            AvatarWidget, LineEdit, PrimaryPushButton)

class AccountInterface(SingleDirectionScrollArea):
    """
    Account Interface: Displays user profile information.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent, orient=Qt.Orientation.Vertical)
        self.view = QWidget(self)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("AccountInterface")
        
        self.v_layout = QVBoxLayout(self.view)
        self.v_layout.setContentsMargins(36, 36, 36, 36)
        self.v_layout.setSpacing(20)
        
        self.view.setStyleSheet("background: transparent;")
        
        self.init_header()
        self.init_profile_card()
        self.init_subscription_card()
        
        self.v_layout.addStretch()

    def init_header(self):
        title = SubtitleLabel("My Account", self)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.v_layout.addWidget(title)
        
        desc = BodyLabel("Manage your personal information and subscription.", self)
        desc.setStyleSheet("color: #666666; font-size: 14px;")
        self.v_layout.addWidget(desc)

    def init_profile_card(self):
        self.v_layout.addSpacing(10)
        
        card = CardWidget(self.view)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header with Avatar
        h_header = QHBoxLayout()
        
        # Large Avatar
        avatar = AvatarWidget("resources/avatar_placeholder.png", card) # Will use default if missing
        avatar.setRadius(32)
        h_header.addWidget(avatar)
        
        # Name & Email
        v_info = QVBoxLayout()
        v_info.setSpacing(2)
        name_lbl = StrongBodyLabel("Trae User", card)
        name_lbl.setStyleSheet("font-size: 18px;")
        email_lbl = BodyLabel("user@example.com", card)
        email_lbl.setStyleSheet("color: #888888;")
        v_info.addWidget(name_lbl)
        v_info.addWidget(email_lbl)
        h_header.addLayout(v_info)
        h_header.addStretch()
        
        btn_edit = PushButton("Edit Profile", card)
        btn_edit.setIcon(FIF.EDIT)
        h_header.addWidget(btn_edit)
        
        layout.addLayout(h_header)
        layout.addSpacing(15)
        
        # Form Fields (Read-only for now)
        self.add_form_row(layout, "Display Name", "Trae User")
        self.add_form_row(layout, "Role", "Senior Translator")
        self.add_form_row(layout, "Organization", "Acme Localization Corp.")
        
        self.v_layout.addWidget(card)

    def init_subscription_card(self):
        self.v_layout.addSpacing(10)
        
        card = CardWidget(self.view)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(StrongBodyLabel("Subscription Plan", card))
        layout.addSpacing(10)
        
        h = QHBoxLayout()
        plan_lbl = BodyLabel("Current Plan: <b>Pro Edition</b>", card)
        h.addWidget(plan_lbl)
        h.addStretch()
        btn_upgrade = PrimaryPushButton("Upgrade", card)
        h.addWidget(btn_upgrade)
        
        layout.addLayout(h)
        self.v_layout.addWidget(card)

    def add_form_row(self, parent_layout, label_text, value_text):
        h = QHBoxLayout()
        lbl = BodyLabel(label_text + ":")
        lbl.setFixedWidth(120)
        val = LineEdit()
        val.setText(value_text)
        val.setReadOnly(True)
        
        h.addWidget(lbl)
        h.addWidget(val)
        parent_layout.addLayout(h)
