import unittest

class TestConverterHTML(unittest.TestCase):
    def test_converter_file_exists_and_contains_elements(self):
        with open('convertisseur.html', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('id="km"', content)
        self.assertIn('id="miles"', content)
        self.assertIn('KM_TO_MILES', content)

if __name__ == '__main__':
    unittest.main()
