import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(r"c:\Users\faruk\Desktop\Code\ninovaNotifier")

from bot.handlers.user.callbacks import handle_course_detail


class TestCourseDetailStats(unittest.TestCase):
    @patch("bot.handlers.user.callbacks.load_saved_grades")
    @patch("bot.handlers.user.callbacks.bot")
    def test_handle_course_detail_stats(self, mock_bot, mock_load_grades):
        """Test if stats logic produces expected output string"""

        # Mock Data
        mock_load_grades.return_value = {
            "12345": {
                "http://test.url": {
                    "course_name": "Test Course",
                    "grades": {
                        "Vize 1": {
                            "not": "80",
                            "agirlik": "40%",
                            "detaylar": {
                                "class_avg": "70",
                                "std_dev": "10",
                                "rank": "5",
                                "student_count": "50",
                            },
                        },
                        "Vize 2": {
                            "not": "90",
                            "agirlik": "60%",
                            "detaylar": {"class_avg": "60", "std_dev": "10"},
                        },
                    },
                }
            }
        }

        # Mock Call
        call = MagicMock()
        call.message.chat.id = 12345
        call.message.message_id = 999
        # det_<course_idx>_<type>
        call.data = "det_0_not"

        # Execute
        handle_course_detail(call)

        # Assertions
        mock_bot.edit_message_text.assert_called()
        __, kwargs = mock_bot.edit_message_text.call_args
        text = kwargs["text"]

        print("Generated Text:\n", text)

        # Check for weight format
        self.assertIn("(%40)", text)
        self.assertIn("(%60)", text)

        # Check for sub-line details
        self.assertIn("Ort: 70", text)
        self.assertIn("Std: 10", text)
        self.assertIn("Sıra: 5", text)

        # Check for cumulative footer
        # User Avg: 0.4*80 + 0.6*90 = 32 + 54 = 86.00
        self.assertIn("Ortalamanız: 86.00", text)

        # Class Avg: 0.4*70 + 0.6*60 = 28 + 36 = 64.00
        self.assertIn("Sınıf geneli: Ort: 64.00", text)

        # Class Std: sqrt((0.4^2 * 10^2) + (0.6^2 * 10^2))
        # = sqrt(0.16*100 + 0.36*100) = sqrt(16 + 36) = sqrt(52) ≈ 7.21
        self.assertIn("Std: 7.21", text)

        # Total Weight
        self.assertIn("(%100 veriye göre)", text)


if __name__ == "__main__":
    unittest.main()
