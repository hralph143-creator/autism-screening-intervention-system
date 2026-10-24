import re
from pydantic import BaseModel, Field, field_validator, model_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{3,32}$")


def validate_password_strength(value: str) -> str:
    if len(value) < 8 or len(value) > 128:
        raise ValueError("密码长度应为 8 至 128 位")
    categories = sum([any(c.islower() for c in value), any(c.isupper() for c in value), any(c.isdigit() for c in value)])
    if categories < 2:
        raise ValueError("密码需至少包含大小写字母、数字中的两类")
    return value


class InitializeRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_is_valid(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("用户名仅支持 3 至 32 位中文、字母、数字或下划线")
        return value

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)

