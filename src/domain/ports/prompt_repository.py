from abc import ABC, abstractmethod
from typing import Generic,TypeVar

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig

T = TypeVar("T")
P = TypeVar("P")

class ConfigRepository(ABC,Generic[T,P]):

    @abstractmethod
    def get(self,key : P) -> T:
        ...

    @abstractmethod
    def watch(self,callback):
        ...


class AgentIdentityRepository(ConfigRepository[AgentIdentity,str]):

    @abstractmethod
    def get(self,key : str) -> AgentIdentity:
        ...

    @abstractmethod
    def watch(self,callback):
        ...



class SkillConfigRepository(ConfigRepository[SkillConfig,str]):

    @abstractmethod
    def get(self,key : str) -> SkillConfig:
        ...

    @abstractmethod
    def watch(self,callback):
        ...