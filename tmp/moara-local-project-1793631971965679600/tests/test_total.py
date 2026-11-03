import unittest
from main import total

class TestTotal(unittest.TestCase):
    def test_total_sum(self):
        self.assertEqual(total(2, 3), 5)

if __name__ == '__main__':
    unittest.main()
