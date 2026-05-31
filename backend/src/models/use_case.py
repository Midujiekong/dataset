"""
用例模型数据类
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class UseCase:
    """用例数据类"""
    name: str
    description: Optional[str] = None
    actors: List[str] = None
    preconditions: List[str] = None
    postconditions: List[str] = None
    main_flow: List[str] = None
    alternative_flows: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.actors is None:
            self.actors = []
        if self.preconditions is None:
            self.preconditions = []
        if self.postconditions is None:
            self.postconditions = []
        if self.main_flow is None:
            self.main_flow = []
        if self.alternative_flows is None:
            self.alternative_flows = []

@dataclass
class UseCaseDiagram:
    """用例图数据类"""
    actors: List[Dict[str, Any]]
    use_cases: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
    def __post_init__(self):
        if self.actors is None:
            self.actors = []
        if self.use_cases is None:
            self.use_cases = []
        if self.relationships is None:
            self.relationships = []
