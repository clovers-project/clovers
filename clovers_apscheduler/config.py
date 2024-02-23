from pydantic import BaseModel


class Config(BaseModel):
    scheduler_config = {"apscheduler.timezone": "Asia/Shanghai"}
