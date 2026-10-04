from typing import get_args

from fastapi import APIRouter

from app.api.dependencies import CurrentUser
from app.schemas import reports

router = APIRouter(tags=["Guided check-up"])


@router.get("/questionnaire")
def questionnaire(user: CurrentUser):
    questions = [
        (
            "clarity",
            "How clear does the water look?",
            "Look from the bank. Cloudiness describes appearance, not a measured turbidity value.",
            reports.Clarity,
        ),
        (
            "smell",
            "Did you notice a smell?",
            "Only report a smell noticed from a safe distance; do not approach or sniff the water.",
            reports.Smell,
        ),
        (
            "flow",
            "How is the water moving?",
            "Still means water is present but not visibly moving. Dry means no visible water at this spot.",
            reports.Flow,
        ),
        (
            "foam",
            "Can you see foam?",
            "Choose small patches or extensive coverage. Foam alone does not identify pollution.",
            reports.Foam,
        ),
        (
            "visible_life",
            "What living things can you see?",
            "None observed means you did not see life; it does not establish that life is absent.",
            reports.VisibleLife,
        ),
        (
            "water_color",
            "What color does the water appear?",
            "Lighting and the streambed can affect color. Choose unknown if unsure.",
            reports.WaterColor,
        ),
    ]
    return {
        "version": "1.0",
        "language": "en",
        "source_note": "Project-defined plain-language fields; not a verified reproduction of the OneAquaHealth app questionnaire.",
        "questions": [
            {
                "field": field,
                "question": question,
                "help": help_text,
                "required": False,
                "options": [
                    {"value": v, "label": v.replace("_", " ").capitalize()} for v in get_args(values)
                ],
            }
            for field, question, help_text, values in questions
        ],
        "measurement": {
            "field": "ph",
            "required": False,
            "minimum": 0,
            "maximum": 14,
            "help": "Enter a value only if measured with suitable equipment. Do not estimate pH from appearance.",
        },
        "photo": {
            "required_for_submission": True,
            "help": "Photograph the stream from a safe accessible bank. Attach at least one photo to submit.",
        },
    }
