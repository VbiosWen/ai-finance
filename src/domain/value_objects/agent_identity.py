
from pydantic import BaseModel,Field

class AgentIdentity(BaseModel):
    persona : str # 品牌/角色身份
    tones : str # 语气风格
    globals_constraints : list[str] = Field(default_factory=list) # 所有skill都要遵守的规范
    output_conventions : str = "" # 通用输入格式约定
    model_config = {"frozen" : True}


    def render(self) -> str:
        parts = [self.persona,f"语气风格:{self.tones}"]
        if self.output_conventions:
            parts.append(f"通用输出规范：\n{self.output_conventions}")
        if self.globals_constraints:
            rules = "\n".join(f"- {c}" for c in self.globals_constraints)
            parts.append(f"全局约束（所有场景均使用）：\n {rules}")
        return "\n\n".join(parts)