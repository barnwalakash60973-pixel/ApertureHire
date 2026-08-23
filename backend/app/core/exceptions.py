"""Custom exceptions. Keeping these distinct lets the API layer map each
failure mode to the right HTTP status instead of a blanket 500."""


class ReviewerError(Exception):
    """Base class for all application-specific errors."""


class DocumentParsingError(ReviewerError):
    """Raised when a DOCX/PDF cannot be read or contains no extractable text."""


class UnsupportedFileTypeError(ReviewerError):
    """Raised when an uploaded file isn't .docx or .pdf."""


class SectionSplitError(ReviewerError):
    """Raised when a document's Part A/B/C/D structure cannot be detected."""


class LLMEvaluationError(ReviewerError):
    """Raised when the LLM call fails or returns an unparseable response."""


class QuestionMatchError(ReviewerError):
    """Raised when a question cannot be reliably matched to an answer."""
