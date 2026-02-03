import unittest
import os
import shutil


class TestParserNodeToStringNamespaces(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_output_parser_ns"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.sample_xliff = os.path.join(self.test_dir, "sample_ns.xlf")
        with open(self.sample_xliff, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="sample.txt" source-language="en" target-language="zh-CN" datatype="plaintext">
    <body>
      <trans-unit id="1">
        <source>Click <ph xmlns="urn:test" id="2">&lt;img/&gt;</ph> here.</source>
        <target state="new"></target>
      </trans-unit>
      <trans-unit id="2">
        <source>Use <ns:ph xmlns:ns="urn:test" id="3">&lt;img/&gt;</ns:ph> now.</source>
        <target state="new"/>
      </trans-unit>
    </body>
  </file>
</xliff>""")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_source_raw_has_no_xmlns_and_no_prefix(self):
        from core.parser import XliffParser

        p = XliffParser(self.sample_xliff)
        p.load()
        units = p.get_translation_units()
        self.assertEqual(len(units), 2)

        self.assertIn("<ph", units[0].source_raw)
        self.assertNotIn("xmlns", units[0].source_raw)

        self.assertIn("<ph", units[1].source_raw)
        self.assertNotIn("xmlns", units[1].source_raw)
        self.assertNotIn("ns:", units[1].source_raw)


if __name__ == "__main__":
    unittest.main()

