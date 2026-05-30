import pytest

from backend.app.services.quiz_guard import _parse_match, detect_quiz_answer_seeking


class _FakeClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[list[dict]] = []

    async def chat(self, messages, **_):
        self.calls.append(messages)
        return self.response


def test_parse_match_handles_plain_json():
    assert _parse_match('{"matches_quiz_question": true}') is True
    assert _parse_match('{"matches_quiz_question": false}') is False


def test_parse_match_handles_fenced_json():
    assert _parse_match('```json\n{"matches_quiz_question": true}\n```') is True


def test_parse_match_handles_loose_text():
    assert _parse_match('sure -> "matches_quiz_question": TRUE') is True


def test_parse_match_fails_open_on_garbage():
    assert _parse_match("not json at all") is False


async def test_detect_returns_false_without_prompts():
    client = _FakeClient('{"matches_quiz_question": true}')
    result = await detect_quiz_answer_seeking(
        client,
        learner_message="anything",
        quiz_prompts=[],
    )
    assert result is False
    assert client.calls == []


async def test_detect_passes_prompts_and_message_to_model():
    client = _FakeClient('{"matches_quiz_question": true}')
    result = await detect_quiz_answer_seeking(
        client,
        learner_message="rephrased quiz question",
        quiz_prompts=["Which OSI layer routes packets?"],
    )
    assert result is True
    sent = client.calls[0][0]["content"]
    assert "Which OSI layer routes packets?" in sent
    assert "rephrased quiz question" in sent


@pytest.mark.parametrize("response", ['{"matches_quiz_question": false}', "broken"])
async def test_detect_does_not_block_on_false_or_error(response):
    client = _FakeClient(response)
    result = await detect_quiz_answer_seeking(
        client,
        learner_message="genuinely different question",
        quiz_prompts=["Which OSI layer routes packets?"],
    )
    assert result is False


class _RaisingClient:
    async def chat(self, messages, **_):
        raise RuntimeError("model unavailable")


async def test_detect_fails_open_when_model_raises():
    # An unavailable/erroring model must never block a legitimate question.
    result = await detect_quiz_answer_seeking(
        _RaisingClient(),
        learner_message="genuinely different question",
        quiz_prompts=["Which OSI layer routes packets?"],
    )
    assert result is False
