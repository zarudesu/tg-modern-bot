"""
Plane API Data Models
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class PlaneUser(BaseModel):
    """Plane workspace member"""
    model_config = ConfigDict(extra="allow")

    id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool = True


class PlaneProject(BaseModel):
    """Plane project"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: Optional[str] = None
    workspace: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlaneState(BaseModel):
    """Plane issue state"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    color: Optional[str] = None
    group: Optional[str] = None  # backlog, unstarted, started, completed, cancelled


class PlaneTask(BaseModel):
    """Plane task (issue) model"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: Optional[str] = None
    state: Union[str, Dict[str, Any]]  # State ID or expanded state object
    state_name: str = "Unknown"
    priority: Optional[str] = "none"
    project: str  # Project ID
    project_name: str = "Unknown"
    sequence_id: Optional[int] = None
    target_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Assignee information (can be list of IDs or list of expanded objects)
    assignees: Union[List[str], List[Dict[str, Any]]] = Field(default_factory=list)
    assignee_name: str = "Unassigned"
    assignee_email: Optional[str] = None

    # Expanded details (when using expand parameter)
    state_detail: Optional[Dict[str, Any]] = None
    project_detail: Optional[Dict[str, Any]] = None
    assignee_details: Optional[Dict[str, Any]] = None

    def get_state_name(self) -> str:
        """Get state name from state_detail or fallback to state_name"""
        if self.state_detail and isinstance(self.state_detail, dict):
            return self.state_detail.get('name', self.state_name)
        return self.state_name

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue"""
        if not self.target_date:
            return False
        try:
            target = datetime.fromisoformat(self.target_date.replace('Z', '+00:00'))
            return target < datetime.now(target.tzinfo)
        except:
            return False

    @property
    def is_due_today(self) -> bool:
        """Check if task is due today"""
        if not self.target_date:
            return False
        try:
            target = datetime.fromisoformat(self.target_date.replace('Z', '+00:00'))
            today = datetime.now(target.tzinfo).date()
            return target.date() == today
        except:
            return False

    @property
    def priority_emoji(self) -> str:
        """Get emoji for priority"""
        priority_map = {
            'urgent': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢',
            'none': '⚪'
        }
        return priority_map.get(self.priority or 'none', '⚪')

    @property
    def state_emoji(self) -> str:
        """Get emoji for state"""
        state_name_lower = self.get_state_name().lower()

        if 'done' in state_name_lower or 'completed' in state_name_lower:
            return '✅'
        elif 'progress' in state_name_lower or 'started' in state_name_lower:
            return '🔄'
        elif 'review' in state_name_lower:
            return '👀'
        elif 'backlog' in state_name_lower:
            return '📋'
        else:
            return '📌'
