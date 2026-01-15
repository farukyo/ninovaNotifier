import io
import sys
import unittest

# Add project root to path
sys.path.append(r"c:\Users\faruk\Desktop\Code\ninovaNotifier")

from services.visualization import generate_bell_curve


class TestVisualization(unittest.TestCase):
    def test_generate_bell_curve(self):
        """Test bell curve generation with mock data"""

        # Mock Data
        grades_data = {
            "Vize 1": {"not": "80", "detaylar": {"class_avg": "70", "std_dev": "10"}},
            "Vize 2": {"not": "50", "detaylar": {"class_avg": "60", "std_dev": "15"}},
            "Odev 1": {
                "not": "100",
                "detaylar": {},  # No stats, should be skipped
            },
        }

        # Execute
        result = generate_bell_curve(grades_data)

        # Assertions
        self.assertIsNotNone(result, "Result should not be None for valid data")
        self.assertIsInstance(result, io.BytesIO, "Result should be BytesIO")

        # Check if content exists
        content = result.getvalue()
        self.assertGreater(len(content), 0, "Image buffer should not be empty")
        print(f"Generated image size: {len(content)} bytes")

    def test_generate_bell_curve_no_stats(self):
        """Test with data lacking statistics"""
        grades_data = {"Odev 1": {"not": "100", "detaylar": {}}}
        result = generate_bell_curve(grades_data)
        self.assertIsNone(result, "Result should be None when no valid stats exist")


if __name__ == "__main__":
    unittest.main()
