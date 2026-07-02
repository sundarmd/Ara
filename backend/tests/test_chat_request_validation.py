import unittest

from pydantic import ValidationError

from models.schemas import ChatRequest


class ChatRequestValidationTests(unittest.TestCase):
    def test_chat_request_rejects_empty_messages(self):
        with self.assertRaises(ValidationError):
            ChatRequest(messages=[])

    def test_chat_request_accepts_at_least_one_message(self):
        request = ChatRequest(messages=[{"role": "user", "content": "Hello"}])

        self.assertEqual(request.messages[0].content, "Hello")
