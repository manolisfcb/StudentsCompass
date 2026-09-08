"""The single list of mapped models.

``Base.metadata`` is only complete once every model module has been imported.
Alembic's autogenerate and the test schema builder both depend on that, and
both used to keep their own hand-maintained import list; a model that landed in
one list and not the other (``roadmapModel`` and ``resumeCourseEvaluationModel``
were missing from Alembic's) became invisible to autogenerate, which then
happily proposed dropping its tables.

Import from here instead of listing modules again. ``test_model_manifest``
walks ``app/models`` and fails if a mapped class is not reachable through
:func:`import_all_models`, so the drift cannot come back silently.
"""
from __future__ import annotations

from app.db import Base
from app.models.aiUsageModel import AIQuotaGrantModel, AIUsageEventModel
from app.models.applicationAnalyticsModel import (
    ApplicationDailyAggregateModel,
    ApplicationStatusEventModel,
)
from app.models.applicationModel import ApplicationModel
from app.models.communityModel import CommunityMemberModel, CommunityModel
from app.models.communityPostModel import (
    CommunityPostCommentModel,
    CommunityPostLikeModel,
    CommunityPostModel,
)
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.emailNotificationLogModel import EmailNotificationLogModel
from app.models.friendshipModel import FriendRequestModel, FriendshipModel
from app.models.interviewAvailabilityModel import InterviewAvailabilityModel
from app.models.jobAnalysisModel import JobAnalysisModel
from app.models.jobPostingModel import JobPosting
from app.models.messageModel import (
    ConversationModel,
    ConversationParticipantModel,
    MessageModel,
)
from app.models.postModel import PostModel
from app.models.questionnaireModel import UserQuestionnaire
from app.models.resourceModel import (
    ResourceEnrollmentModel,
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
)
from app.models.resumeCourseEvaluationModel import ResumeCourseEvaluationModel
from app.models.resumeEmbeddingsModel import ResumeEmbedding
from app.models.resumeModel import ResumeModel
from app.models.roadmapModel import (
    RoadmapModel,
    RoadmapStageModel,
    StageProjectModel,
    StageTaskModel,
    UserProjectSubmissionModel,
    UserRoadmapModel,
    UserStageProgressModel,
    UserTaskProgressModel,
)
from app.models.storageDeletionIntentModel import StorageDeletionIntentModel
from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    JobSkillModel,
    OptimizationRunModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.models.userModel import User
from app.models.userStatsModel import UserStatsModel

ALL_MODELS = (
    AIQuotaGrantModel,
    AIUsageEventModel,
    ApplicationDailyAggregateModel,
    ApplicationModel,
    ApplicationStatusEventModel,
    CommunityMemberModel,
    CommunityModel,
    CommunityPostCommentModel,
    CommunityPostLikeModel,
    CommunityPostModel,
    Company,
    CompanyRecruiter,
    ConversationModel,
    ConversationParticipantModel,
    CourseModel,
    CourseSkillModel,
    EmailNotificationLogModel,
    FriendRequestModel,
    FriendshipModel,
    InterviewAvailabilityModel,
    JobAnalysisModel,
    JobPosting,
    JobSkillModel,
    MessageModel,
    OptimizationRunModel,
    PostModel,
    ResourceEnrollmentModel,
    ResourceLessonModel,
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
    ResumeCourseEvaluationModel,
    ResumeEmbedding,
    ResumeModel,
    ResumeSkillModel,
    RoadmapModel,
    RoadmapStageModel,
    SkillAliasModel,
    SkillModel,
    StageProjectModel,
    StageTaskModel,
    StorageDeletionIntentModel,
    User,
    UserProjectSubmissionModel,
    UserQuestionnaire,
    UserRoadmapModel,
    UserStageProgressModel,
    UserStatsModel,
    UserTaskProgressModel,
)


def import_all_models():
    """Return ``Base`` with every mapped model registered on its metadata."""
    return Base


__all__ = ["ALL_MODELS", "Base", "import_all_models"]
