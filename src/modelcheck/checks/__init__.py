"""Все проверки. Каждая — в своей папке: check.py + README.md. Порядок = порядок в отчёте."""
from .model_field import check as _model_field  # noqa: F401
from .thinking_signature import check as _thinking  # noqa: F401
from .response_shape import check as _shape  # noqa: F401
from .hidden_prompt import check as _hidden  # noqa: F401
from .reasoning import check as _reasoning  # noqa: F401
from .identity import check as _identity  # noqa: F401
from .late_turns import check as _late  # noqa: F401
from .tokenizer import check as _tokenizer  # noqa: F401
from .capabilities import check as _caps  # noqa: F401
from .random_number import check as _numbers  # noqa: F401
from .forty_questions import check as _forty  # noqa: F401
