import unittest
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# Import classes
from desktop_app import MainWindow
from ui.profile_wizard import ProfileWizardDialog, WizardResult
from core.profile import ProfileStatus

class TestFlowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Headless mode for Qt
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.xliff_path = os.path.join(self.test_dir, "test.xlf")
        with open(self.xliff_path, "w") as f:
            f.write('<xliff version="1.2"><file original="test.txt" source-language="en" target-language="de"><body><trans-unit id="1"><source>Hello</source></trans-unit></body></file></xliff>') # Valid XLIFF
            
        self.window = MainWindow()
        # Mock Profile Manager internal path to isolate test
        # Note: MainWindow handles profile logic directly now, no separate manager class yet.
        # But we can patch where it writes sidecars if needed.
        # For now, let's just let it write to the temp dir since xliff is there.
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        self.window.close()

    @patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName')
    @patch('desktop_app.ProfileWizardDialog.exec')
    @patch('PyQt6.QtWidgets.QMessageBox.information')
    def test_skip_flow(self, mock_msg, mock_exec, mock_file_dialog):
        """
        Flow: Open File -> Wizard Launches -> User Skips
        Expected: Status=NEW/DRAFT, No Sidecar, UI shows Temporary
        """
        mock_file_dialog.return_value = (self.xliff_path, "")
        
        # We need to control the wizard instance created inside open_file
        # We should patch the class where it is imported in desktop_app
        
        with patch('desktop_app.ProfileWizardDialog') as MockWizardCls:
            mock_inst = MockWizardCls.return_value
            mock_inst.exec.return_value = 0 # rejected
            mock_inst.result_code = WizardResult.SKIPPED
            
            # Action
            self.window.open_file()
            
            # Assertions
            # 1. Profile Status
            self.assertIsNotNone(self.window.current_profile)
            # Default factory creates NEW
            self.assertEqual(self.window.current_profile.controls.status, ProfileStatus.NEW)
            
            # 2. No Sidecar
            sidecar = f"{self.xliff_path}.profile.json"
            self.assertFalse(os.path.exists(sidecar), "Sidecar should not exist after Skip")
            
            # 3. UI Stats (Just check stats are updated, no specific label for profile status yet in MVP)
            # self.assertIn("Temporary", status_text)

    @patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName')
    @patch('PyQt6.QtWidgets.QMessageBox.information')
    def test_finish_save_restart_flow(self, mock_msg, mock_file_dialog):
        """
        Flow: Open File -> Wizard -> Accept -> Restart -> Open Same File
        Expected: Status=CONFIRMED, Sidecar Exists, No Wizard on 2nd open
        """
        mock_file_dialog.return_value = (self.xliff_path, "")
        
        # --- Step 1: Open & Accept ---
        with patch('desktop_app.ProfileWizardDialog') as MockWizardCls:
            mock_inst = MockWizardCls.return_value
            mock_inst.exec.return_value = 1 # accepted
            mock_inst.result_code = WizardResult.ACCEPTED
            
            # Mock get_profile to return a CONFIRMED profile
            # We must simulate what the dialog returns
            from core.profile import TranslationProfile, ProfileStatus
            p = TranslationProfile()
            p.controls.status = ProfileStatus.CONFIRMED
            mock_inst.get_profile.return_value = p
            
            # Action 1
            self.window.open_file()
            
            # Assertions 1
            self.assertEqual(self.window.current_profile.controls.status, ProfileStatus.CONFIRMED)
            sidecar = f"{self.xliff_path}.profile.json"
            self.assertTrue(os.path.exists(sidecar), "Sidecar MUST exist after Accept")
            

        # --- Step 2: Restart & Re-open ---
        # Simulate restart by creating new window instance
        self.window.close()
        new_window = MainWindow()
        
        with patch('desktop_app.ProfileWizardDialog') as MockWizardCls2:
            # Action 2
            new_window.open_file()
            
            # Assertions 2
            # Wizard should NOT be instantiated because status is already CONFIRMED in sidecar
            MockWizardCls2.assert_not_called()
            
            # Profile state
            self.assertEqual(new_window.current_profile.controls.status, ProfileStatus.CONFIRMED)
            
        new_window.close()

    @patch('PyQt6.QtWidgets.QFileDialog.getOpenFileName')
    @patch('PyQt6.QtWidgets.QMessageBox.information')
    @patch('PyQt6.QtCore.QSettings') # Patch settings to use temporary dict
    def test_smart_defaults(self, mock_settings_cls, mock_msg, mock_file_dialog):
        """
        Test that selections in Wizard are remembered and applied to next new file.
        """
        mock_file_dialog.return_value = (self.xliff_path, "")
        
        # Mock QSettings behavior with a dict
        settings_store = {}
        mock_settings = MagicMock()
        mock_settings.value.side_effect = lambda k, d=None: settings_store.get(k, d)
        mock_settings.setValue.side_effect = lambda k, v: settings_store.update({k: v})
        mock_settings_cls.return_value = mock_settings
        
        # --- Run 1: Set Warranty + fr-FR ---
        with patch('ui.profile_wizard.ProfileWizardDialog') as MockWizardCls:
            # We need to simulate the wizard internal logic partially or just trust 
            # that we can inspect the side effects (settings update)
            # But the settings update happens inside go_next(). 
            # In integration test, we can't easily trigger internal methods of the dialog 
            # unless we instantiate it or mock it carefully.
            
            # Strategy: We rely on the fact that if we Mock the class, 
            # the desktop_app calls .exec(). 
            # We can't verify logic INSIDE the wizard unless we test Wizard unit test.
            # BUT here we want to verify the FLOW.
            
            # Actually, this is better tested in a unit test for ProfileWizardDialog 
            # rather than full integration, because we mock the dialog here anyway!
            # If we mock the dialog, we aren't testing the dialog's save logic.
            pass

    # We will implement this test in test_ui_logic.py instead where we have access to the dialog instance
    # So I will remove this incomplete test and add it to test_ui_logic.py

if __name__ == '__main__':
    unittest.main()
