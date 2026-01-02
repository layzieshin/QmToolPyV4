"""Controllers for documents module.

Coordinate UI actions and business logic.
Stateless, testable, no tkinter dependencies.
"""

from documents.controllers.search_filter_controller import SearchFilterController
from documents.controllers.document_list_controller import DocumentListController
from documents.controllers.document_details_controller import DocumentDetailsController
from documents.controllers.document_creation_controller import DocumentCreationController
from documents.controllers.workflow_controller import WorkflowController
from documents.controllers.assignment_controller import AssignmentController

__all__ = [
    "SearchFilterController",
    "DocumentListController",
    "DocumentDetailsController",
    "DocumentCreationController",
    "WorkflowController",
    "AssignmentController",
]