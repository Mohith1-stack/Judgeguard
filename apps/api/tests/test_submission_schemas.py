import pytest
from pydantic import ValidationError

from app.models import SubmissionQuestionType
from app.schemas.submission import SubmissionQuestionCreate, SubmissionUpsert


def test_text_question_requires_no_options():
    question = SubmissionQuestionCreate(
        key="project_goal",
        label="Project goal",
        question_type=SubmissionQuestionType.TEXT,
    )
    assert question.options == []


def test_selection_question_requires_options():
    with pytest.raises(ValidationError):
        SubmissionQuestionCreate(
            key="track_choice",
            label="Choose a track",
            question_type=SubmissionQuestionType.SINGLE_SELECT,
        )


def test_selection_question_accepts_options():
    question = SubmissionQuestionCreate(
        key="track_choice",
        label="Choose a track",
        question_type=SubmissionQuestionType.SINGLE_SELECT,
        options=["Cyber", "AI"],
    )
    assert question.options == ["Cyber", "AI"]


def test_submission_normalizes_tags():
    submission = SubmissionUpsert(
        name="Project",
        tech_tags=[" Python ", "PYTHON", "FastAPI"],
        custom_answers={},
    )
    assert submission.tech_tags == ["python", "fastapi"]
