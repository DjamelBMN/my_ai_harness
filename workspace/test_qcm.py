import unittest

class TestQCMMaths(unittest.TestCase):
    def test_qcm_structure(self):
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('QCM de Mathématiques', content)
        self.assertIn('question-card', content)
        self.assertIn('correction-', content)

if __name__ == '__main__':
    unittest.main()
