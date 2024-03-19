from pydantic import BaseModel


class Item(BaseModel):
    id: str = ""
    name: str = ""


class Prop(Item):
    rare: int
    """稀有度"""
    domain: int
    """
    作用域   
        0:无(空气)
        1:群内
        2:全局
    """
    flow: int
    """
    道具时效
        0:永久道具
        1:时效道具
    """
    number: int
    """道具编号"""
    color: str = "black"
    intro: str = ""
    tip: str = ""

    def __init__(self, id: str, **data) -> None:
        data.update(self.code_info(id))
        super().__init__(**data)

    @staticmethod
    def code_info(id: str):
        rare = int(id[0])
        domain = int(id[1])
        flow = int(id[2])
        number = int(id[3:])
        return {
            "rare": rare,
            "domain": domain,
            "flow": flow,
            "number": number,
        }


a = Prop("1234")
