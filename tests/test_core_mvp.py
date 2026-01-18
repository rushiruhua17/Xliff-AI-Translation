import unittest
import os
import shutil
from core.parser import XliffParser
from core.abstractor import TagAbstractor, AbstractionResult

class TestCoreMVP(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_output"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        self.sample_xliff = os.path.join(self.test_dir, "sample.xlf")
        with open(self.sample_xliff, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.txt" source-language="en" target-language="zh-CN" datatype="plaintext">
    <body>
      <trans-unit id="1">
        <source>Hello <bpt id="1">&lt;b&gt;</bpt>World<ept id="1">&lt;/b&gt;</ept>!</source>
        <target state="new"></target>
      </trans-unit>
      <trans-unit id="2">
        <source>Click <ph id="2">&lt;img src="icon.png"/&gt;</ph> here.</source>
        <target state="new"/>
      </trans-unit>
    </body>
  </file>
</xliff>""")

    def test_roundtrip(self):
        # 1. Parse
        parser = XliffParser(self.sample_xliff)
        parser.load()
        units = parser.get_translation_units()
        
        self.assertEqual(len(units), 2)
        self.assertIn('<bpt id="1">&lt;b&gt;</bpt>', units[0].source_raw)
        
        # 2. Abstract
        abstractor = TagAbstractor()
        for u in units:
            res = abstractor.abstract(u.source_raw)
            u.source_abstracted = res.abstracted_text
            u.tags_map = res.tags_map
        
        # Check abstraction
        print(f"Unit 1 Abstracted: {units[0].source_abstracted}")
        self.assertEqual(units[0].source_abstracted, "Hello {1}World{2}!")
        self.assertEqual(units[1].source_abstracted, "Click {1} here.")
        
        # 3. Simulate AI Translation (Manual)
        # Unit 1: Hello {1}World{2}! -> 你好 {1}世界{2}！
        units[0].target_abstracted = "你好 {1}世界{2}！"
        # Unit 2: Click {1} here. -> 点击 {1} 这里。
        units[1].target_abstracted = "点击 {1} 这里。"
        
        # 4. Reconstruct
        for u in units:
            u.target_raw = abstractor.reconstruct(u.target_abstracted, u.tags_map)
            
        print(f"Unit 1 Reconstructed: {units[0].target_raw}")
        self.assertIn('<bpt id="1">&lt;b&gt;</bpt>', units[0].target_raw)
        self.assertIn('世界', units[0].target_raw)
        
        # 5. Validation Check
        from core.validator import Validator
        validator = Validator()
        errors = validator.validate_structure(units[0])
        self.assertEqual(len(errors), 0)
        
        # Test error case
        units[0].target_abstracted = "你好 世界" # Missing tags
        errors = validator.validate_structure(units[0])
        self.assertGreater(len(errors), 0)
        print(f"Validation Errors (Expected): {errors}")
        
        # Restore for file update
        units[0].target_abstracted = "你好 {1}世界{2}！"
        units[0].target_raw = abstractor.reconstruct(units[0].target_abstracted, units[0].tags_map)

        # 6. Update File
        output_path = os.path.join(self.test_dir, "translated.xlf")
        parser.update_targets(units, output_path)
        
        # Verify Output File
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn('你好 <bpt id="1">&lt;b&gt;</bpt>世界<ept id="1">&lt;/b&gt;</ept>！', content)

if __name__ == "__main__":
    unittest.main()
