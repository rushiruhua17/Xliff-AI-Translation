
import unittest
import os
import json
import time
import shutil
from core.autosave import Autosaver
from core.xliff_obj import TranslationUnit

class TestAutosaveIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests_temp"
        os.makedirs(self.test_dir, exist_ok=True)
        self.xliff_path = os.path.join(self.test_dir, "test.xlf")
        
        # Create a dummy XLIFF file
        with open(self.xliff_path, "w", encoding="utf-8") as f:
            f.write("<xliff><file><body><trans-unit id='1'><source>Hello</source></trans-unit></body></file></xliff>")
            
        self.autosaver = Autosaver(self.xliff_path)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_autosave_flow(self):
        # 1. Create units
        units = [
            TranslationUnit("1", "Hello", "", "new"),
            TranslationUnit("2", "World", "", "new")
        ]
        
        # 2. Simulate translation
        units[0].target_abstracted = "你好"
        units[0].state = "translated"
        
        # 3. Save patch
        self.autosaver.save_patch(units)
        
        # 4. Check file existence
        autosave_path = self.autosaver.autosave_path
        self.assertTrue(os.path.exists(autosave_path), "Autosave file should exist")
        
        # 5. Check content
        with open(autosave_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertEqual(data["original_file"], self.xliff_path)
        self.assertIn("1", data["units"])
        self.assertEqual(data["units"]["1"]["target"], "你好")
        self.assertNotIn("2", data["units"], "Should not save untranslated units")
        
        # 6. Check recovery detection
        recovery = self.autosaver.check_recovery_available()
        self.assertIsNotNone(recovery)
        self.assertEqual(recovery["units"]["1"]["target"], "你好")

    def test_fingerprint_mismatch(self):
        # 1. Save valid patch
        units = [TranslationUnit("1", "Hello", "你好", "translated")]
        self.autosaver.save_patch(units)
        
        # 2. Modify original file (simulating a different file with same name)
        with open(self.xliff_path, "a", encoding="utf-8") as f:
            f.write("<!-- Modified -->")
            
        # Re-init autosaver to calc new fingerprint
        new_autosaver = Autosaver(self.xliff_path)
        
        # 3. Check recovery - should be rejected
        recovery = new_autosaver.check_recovery_available()
        self.assertIsNone(recovery, "Should reject recovery if file changed")

if __name__ == "__main__":
    unittest.main()
