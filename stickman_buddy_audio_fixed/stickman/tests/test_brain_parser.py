import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brain import parse_action_reply


class TestAIResponse(unittest.TestCase):
    def test_valid_reply(self):
        self.assertEqual(parse_action_reply('{"action":" WAVE ","say":"Hi!"}', ["wave"]),
                         {"action": "wave", "say": "Hi!"})

    def test_refuses_unapproved_action(self):
        self.assertIsNone(parse_action_reply('{"action":"skip_song","say":"hi"}', ["wave"]))

    def test_bad_json_and_wrong_shape(self):
        self.assertIsNone(parse_action_reply("not json", ["wave"]))
        self.assertIsNone(parse_action_reply('[]', ["wave"]))

    def test_limits_speech(self):
        result = parse_action_reply('{"action":"wave","say":"' + 'x' * 80 + '"}', ["wave"])
        self.assertEqual(len(result["say"]), 60)


if __name__ == "__main__":
    unittest.main()
