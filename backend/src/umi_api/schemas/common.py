from typing import Literal

from umi_api.schemas.base import ApiModel


class Scores(ApiModel):
    comfort: int
    safety: int
    air: int
    noise: int


class Ok(ApiModel):
    ok: Literal[True] = True
