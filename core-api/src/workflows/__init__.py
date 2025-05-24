"""
Workflow modules for agent-based processing
Migrated from services/query/agent-service/src/workflows/
"""

from .bug_detection import BugDetectionWorkflow
from .feature_request import FeatureRequestWorkflow
from .training import TrainingWorkflow

__all__ = [
    'BugDetectionWorkflow',
    'FeatureRequestWorkflow', 
    'TrainingWorkflow'
] 