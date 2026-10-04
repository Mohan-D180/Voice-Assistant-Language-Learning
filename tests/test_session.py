import unittest

from companion.session import Session


class SessionTests(unittest.TestCase):
    def test_system_prompt_follows_language_and_mode(self):
        s = Session("bn")
        self.assertIn("Bengali", s.messages()[0]["content"])
        s.set_language("de")
        self.assertIn("German", s.messages()[0]["content"])
        s.set_mode("tutor")
        self.assertIn("tutor", s.messages()[0]["content"])

    def test_unknown_values_fall_back(self):
        s = Session("xx", "weird")
        self.assertEqual(s.language.code, "en")
        self.assertEqual(s.mode, "chat")

    def test_history_is_trimmed_and_starts_with_user(self):
        s = Session("en", max_turns=2)
        for i in range(5):
            s.add_user(f"u{i}")
            s.add_assistant(f"a{i}")
        msgs = s.messages()
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual([m["content"] for m in msgs[1:]], ["u3", "a3", "u4", "a4"])

    def test_empty_assistant_reply_is_ignored(self):
        s = Session("en")
        s.add_user("hi")
        s.add_assistant("   ")
        self.assertEqual(len(s.messages()), 2)

    def test_reset(self):
        s = Session("en")
        s.add_user("hi")
        s.reset()
        self.assertEqual(len(s.messages()), 1)


if __name__ == "__main__":
    unittest.main()
