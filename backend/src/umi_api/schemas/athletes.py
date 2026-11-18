from umi_api.schemas.base import ApiModel


class Athlete(ApiModel):
    id: str
    name: str
    first_name: str
    initials: str
    age: int
    city: str
    vehicle: str
