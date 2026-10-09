from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from typing import Literal

MAX_PRICE_CENTS = 100_000_000
URL_PATTERN = r"^https?://\S+$"
MAX_TAGS = 10
MAX_TAG_LENGTH = 30

def normalize_tags(tags: list[str] | None) -> list[str] | None:
    if tags is None:
        return None

    normalized = []

    for tag in tags:
        tag = " ".join(tag.split()).lower()

        if not 1 <= len(tag) <= MAX_TAG_LENGTH:
            raise ValueError(f"each tag must have between 1 and {MAX_TAG_LENGTH} characters")

        if tag not in normalized:
            normalized.append(tag)

    if len(normalized) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags are allowed")

    return normalized

class OfferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_name: str = Field(min_length=2, max_length=200)
    url: str = Field(max_length=2048, pattern=URL_PATTERN)
    message: str | None = Field(default=None, max_length=4000)
    original_price_cents: int = Field(gt=0, le=MAX_PRICE_CENTS, strict=True)
    price_cents: int = Field(gt=0, le=MAX_PRICE_CENTS, strict=True)
    tags: list[str] = Field(default_factory=list)

    _tags = field_validator("tags")(normalize_tags)

    @model_validator(mode="after")
    def check_prices(self) -> "OfferCreate":
        if self.price_cents > self.original_price_cents:
            raise ValueError("price_cents must be less than or equal to original_price_cents")

        return self

class OfferUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_name: str | None = Field(default=None, min_length=2, max_length=200)
    url: str | None = Field(default=None, max_length=2048, pattern=URL_PATTERN)
    message: str | None = Field(default=None, max_length=4000)
    original_price_cents: int | None = Field(default=None, gt=0, le=MAX_PRICE_CENTS, strict=True)
    price_cents: int | None = Field(default=None, gt=0, le=MAX_PRICE_CENTS, strict=True)
    status: Literal["draft", "archived"] | None = None
    tags: list[str] | None = None

    _tags = field_validator("tags")(normalize_tags)

    @model_validator(mode="after")
    def reject_nulls(self) -> "OfferUpdate":
        for field in ("product_name", "url", "original_price_cents", "price_cents", "status", "tags"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")

        return self

def format_validation_error(error: ValidationError) -> str:
    first = error.errors()[0]
    message = first["msg"].removeprefix("Value error, ")
    field = ".".join(str(part) for part in first["loc"])

    return f"{field}: {message}" if field else message