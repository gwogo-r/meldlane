from enum import Enum

from pydantic import BaseModel, Field


class MemberKind(str, Enum):
    human = "human"
    agent = "agent"


class Member(BaseModel):
    id: str
    name: str
    kind: MemberKind
    role: str | None = None
    aliases: list[str] = Field(default_factory=list)  # др. написания имени (кириллица, сокращения)

    # human: недельная ёмкость в story points
    capacity_sp: float | None = None

    # agent: провайдер/модель и цена $/1M токенов — основа расчёта стоимости
    provider: str | None = None
    model: str | None = None
    price_in: float | None = None
    price_out: float | None = None
