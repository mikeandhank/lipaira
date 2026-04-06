"""Skill registry - auto-registers all skills."""

from skills.registry import SkillRegistry, BaseSkill, skill_registry

# Import all skills to register them
from skills.email.send import EmailSendSkill, EmailDraftSkill
from skills.quickbooks.get_invoices import QuickBooksGetInvoicesSkill
from skills.quickbooks.get_customers import QuickBooksGetCustomersSkill
from skills.google.calendar import CalendarGetEventsSkill
from skills.google.business_profile import GoogleBusinessUpdateSkill
from skills.google.ads import GoogleAdsGetCampaignsSkill
from skills.google.gmail import GmailReadSkill, GmailSendSkill
from skills.memory.recall import MemoryRecallSkill
from skills.memory.store import MemoryStoreSkill

# New integrations (from INTEGRATIONS.md spec)
from skills.zoom.meetings import ZoomGetMeetingsSkill, ZoomCreateMeetingSkill
from skills.calendly.scheduling import CalendlyGetScheduledEventsSkill, CalendlyGetEventTypesSkill
from skills.meta.ads import MetaGetAdPerformanceSkill, MetaGetCampaignsSkill
from skills.canva.designs import CanvaGetDesignsSkill, CanvaCreateDesignSkill
from skills.trello.boards import TrelloGetCardsSkill, TrelloCreateCardSkill
from skills.asana.tasks import AsanaGetTasksSkill, AsanaCreateTaskSkill

# Register all skills
skill_registry.register(EmailSendSkill)
skill_registry.register(EmailDraftSkill)
skill_registry.register(QuickBooksGetInvoicesSkill)
skill_registry.register(QuickBooksGetCustomersSkill)
skill_registry.register(CalendarGetEventsSkill)
skill_registry.register(GoogleBusinessUpdateSkill)
skill_registry.register(GoogleAdsGetCampaignsSkill)
skill_registry.register(GmailReadSkill)
skill_registry.register(GmailSendSkill)
skill_registry.register(MemoryRecallSkill)
skill_registry.register(MemoryStoreSkill)

# Register Notion skills
from skills.notion import NotionSearchSkill, NotionCreatePageSkill
skill_registry.register(NotionSearchSkill)
skill_registry.register(NotionCreatePageSkill)

# Register web skills
from skills.web_search import WebSearchSkill
from skills.web_fetch import WebFetchSkill
skill_registry.register(WebSearchSkill)
skill_registry.register(WebFetchSkill)

# Register Square skills
from skills.square import SquareInvoiceCreateSkill, SquareCustomerLookupSkill, SquareAppointmentListSkill
skill_registry.register(SquareInvoiceCreateSkill)
skill_registry.register(SquareCustomerLookupSkill)
skill_registry.register(SquareAppointmentListSkill)

# Register Slack skills
from skills.slack import SlackPostSkill, SlackReadChannelSkill, SlackDMSendSkill
skill_registry.register(SlackPostSkill)
skill_registry.register(SlackReadChannelSkill)
skill_registry.register(SlackDMSendSkill)

# Register Discord skill
from skills.discord import DiscordSendSkill
skill_registry.register(DiscordSendSkill)

# Register GitHub skill
from skills.github import GitHubSkill
skill_registry.register(GitHubSkill)

# Register CRM skills
from skills.crm import CRMContactLookupSkill, CRMContactCreateSkill, CRMDealCreateSkill, CRMPipelineSummarySkill
skill_registry.register(CRMContactLookupSkill)
skill_registry.register(CRMContactCreateSkill)
skill_registry.register(CRMDealCreateSkill)
skill_registry.register(CRMPipelineSummarySkill)

# Register YouTube skill
from skills.youtube import YouTubeTranscriptSkill
skill_registry.register(YouTubeTranscriptSkill)

# Register grocery ordering (Item 11)
from skills.grocery import GroceryOrderingSkill
skill_registry.register(GroceryOrderingSkill)

# Register restaurant reservation (Item 12)
from skills.restaurant import RestaurantReservationSkill
skill_registry.register(RestaurantReservationSkill)

# Register new skills
skill_registry.register(ZoomGetMeetingsSkill)
skill_registry.register(ZoomCreateMeetingSkill)
skill_registry.register(CalendlyGetScheduledEventsSkill)
skill_registry.register(CalendlyGetEventTypesSkill)
skill_registry.register(MetaGetAdPerformanceSkill)
skill_registry.register(MetaGetCampaignsSkill)
skill_registry.register(CanvaGetDesignsSkill)
skill_registry.register(CanvaCreateDesignSkill)
skill_registry.register(TrelloGetCardsSkill)
skill_registry.register(TrelloCreateCardSkill)
skill_registry.register(AsanaGetTasksSkill)
skill_registry.register(AsanaCreateTaskSkill)

__all__ = [
    "skill_registry",
    "SkillRegistry",
    "BaseSkill",
]