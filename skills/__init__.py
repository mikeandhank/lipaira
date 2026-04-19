"""Skill registry - auto-registers all skills."""
import logging

logger = logging.getLogger(__name__)

from skills.registry import SkillRegistry, BaseSkill, skill_registry

# === Email Skills ===
try:
 from skills.email.send import EmailSendSkill, EmailDraftSkill
 skill_registry.register(EmailSendSkill)
 skill_registry.register(EmailDraftSkill)
except Exception as e:
 logger.warning(f"Failed to load email skills: {e}")

# === QuickBooks Skills ===
try:
 from skills.quickbooks.get_invoices import QuickBooksGetInvoicesSkill
 from skills.quickbooks.get_customers import QuickBooksGetCustomersSkill
 skill_registry.register(QuickBooksGetInvoicesSkill)
 skill_registry.register(QuickBooksGetCustomersSkill)
except Exception as e:
 logger.warning(f"Failed to load QuickBooks skills: {e}")

# === Google Skills ===
try:
 from skills.google.calendar import CalendarGetEventsSkill
 from skills.google.business_profile import GoogleBusinessUpdateSkill
 from skills.google.ads import GoogleAdsGetCampaignsSkill
 from skills.google.gmail import GmailReadSkill, GmailSendSkill
 skill_registry.register(CalendarGetEventsSkill)
 skill_registry.register(GoogleBusinessUpdateSkill)
 skill_registry.register(GoogleAdsGetCampaignsSkill)
 skill_registry.register(GmailReadSkill)
 skill_registry.register(GmailSendSkill)
except Exception as e:
 logger.warning(f"Failed to load Google skills: {e}")

# === Memory Skills ===
try:
 from skills.memory.recall import MemoryRecallSkill
 from skills.memory.store import MemoryStoreSkill
 skill_registry.register(MemoryRecallSkill)
 skill_registry.register(MemoryStoreSkill)
except Exception as e:
 logger.warning(f"Failed to load memory skills: {e}")

# === Notion Skills ===
try:
 from skills.notion import NotionSearchSkill, NotionCreatePageSkill
 skill_registry.register(NotionSearchSkill)
 skill_registry.register(NotionCreatePageSkill)
except Exception as e:
 logger.warning(f"Failed to load Notion skills: {e}")

# === Web Skills ===
try:
 from skills.web_search import WebSearchSkill
 from skills.web_fetch import WebFetchSkill
 skill_registry.register(WebSearchSkill)
 skill_registry.register(WebFetchSkill)
except Exception as e:
 logger.warning(f"Failed to load web skills: {e}")

# === Square Skills ===
try:
 from skills.square import SquareInvoiceCreateSkill, SquareCustomerLookupSkill, SquareAppointmentListSkill
 skill_registry.register(SquareInvoiceCreateSkill)
 skill_registry.register(SquareCustomerLookupSkill)
 skill_registry.register(SquareAppointmentListSkill)
except Exception as e:
 logger.warning(f"Failed to load Square skills: {e}")

# === Square Skill (lipaira_client) ===
try:
    from lipaira_client.skills import square_skill
    skill_registry.register(square_skill)
except Exception as e:
    logger.warning(f"Failed to load lipaira_client square_skill: {e}")

# === Slack Skills ===
try:
    from skills.slack import SlackPostSkill, SlackReadChannelSkill, SlackDMSendSkill
    skill_registry.register(SlackPostSkill)
    skill_registry.register(SlackReadChannelSkill)
    skill_registry.register(SlackDMSendSkill)
except Exception as e:
 logger.warning(f"Failed to load Slack skills: {e}")

# === Slack Skill (lipaira_client) ===
try:
    from lipaira_client.skills import slack_skill
    skill_registry.register(slack_skill)
except Exception as e:
    logger.warning(f"Failed to load lipaira_client slack_skill: {e}")

# === Discord Skill ===
try:
 from skills.discord import DiscordSendSkill
 skill_registry.register(DiscordSendSkill)
except Exception as e:
 logger.warning(f"Failed to load Discord skill: {e}")

# === GitHub Skill ===
try:
 from skills.github import GitHubSkill
 skill_registry.register(GitHubSkill)
except Exception as e:
 logger.warning(f"Failed to load GitHub skill: {e}")

# === CRM Skills ===
try:
 from skills.crm import CRMContactLookupSkill, CRMContactCreateSkill, CRMDealCreateSkill, CRMPipelineSummarySkill
 skill_registry.register(CRMContactLookupSkill)
 skill_registry.register(CRMContactCreateSkill)
 skill_registry.register(CRMDealCreateSkill)
 skill_registry.register(CRMPipelineSummarySkill)
except Exception as e:
 logger.warning(f"Failed to load CRM skills: {e}")

# === YouTube Skill ===
try:
 from skills.youtube import YouTubeTranscriptSkill
 skill_registry.register(YouTubeTranscriptSkill)
except Exception as e:
 logger.warning(f"Failed to load YouTube skill: {e}")

# === Grocery Ordering Skill ===
try:
 from skills.grocery import GroceryOrderingSkill
 skill_registry.register(GroceryOrderingSkill)
except Exception as e:
 logger.warning(f"Failed to load grocery skill: {e}")

# === Restaurant Reservation Skill ===
try:
 from skills.restaurant import RestaurantReservationSkill
 skill_registry.register(RestaurantReservationSkill)
except Exception as e:
 logger.warning(f"Failed to load restaurant skill: {e}")

# === Zoom Skills ===
try:
 from skills.zoom.meetings import ZoomGetMeetingsSkill, ZoomCreateMeetingSkill
 skill_registry.register(ZoomGetMeetingsSkill)
 skill_registry.register(ZoomCreateMeetingSkill)
except Exception as e:
 logger.warning(f"Failed to load Zoom skills: {e}")

# === Calendly Skills ===
try:
 from skills.calendly.scheduling import CalendlyGetScheduledEventsSkill, CalendlyGetEventTypesSkill
 skill_registry.register(CalendlyGetScheduledEventsSkill)
 skill_registry.register(CalendlyGetEventTypesSkill)
except Exception as e:
 logger.warning(f"Failed to load Calendly skills: {e}")

# === Meta/Facebook Ads Skills ===
try:
 from skills.meta.ads import MetaGetAdPerformanceSkill, MetaGetCampaignsSkill
 skill_registry.register(MetaGetAdPerformanceSkill)
 skill_registry.register(MetaGetCampaignsSkill)
except Exception as e:
 logger.warning(f"Failed to load Meta skills: {e}")

# === Canva Skills ===
try:
 from skills.canva.designs import CanvaGetDesignsSkill, CanvaCreateDesignSkill
 skill_registry.register(CanvaGetDesignsSkill)
 skill_registry.register(CanvaCreateDesignSkill)
except Exception as e:
 logger.warning(f"Failed to load Canva skills: {e}")

# === Trello Skills ===
try:
 from skills.trello.boards import TrelloGetCardsSkill, TrelloCreateCardSkill
 skill_registry.register(TrelloGetCardsSkill)
 skill_registry.register(TrelloCreateCardSkill)
except Exception as e:
 logger.warning(f"Failed to load Trello skills: {e}")

# === Asana Skills ===
try:
 from skills.asana.tasks import AsanaGetTasksSkill, AsanaCreateTaskSkill
 skill_registry.register(AsanaGetTasksSkill)
 skill_registry.register(AsanaCreateTaskSkill)
except Exception as e:
 logger.warning(f"Failed to load Asana skills: {e}")

# === Microsoft Skills ===
try:
 from skills.microsoft import OutlookSendSkill, OutlookReadSkill, OutlookCalendarReadSkill, OutlookCalendarWriteSkill, OneDriveUploadSkill, WordCreateSkill, ExcelCreateSkill, OneNoteCreateSkill, OutlookContactLookupSkill
 skill_registry.register(OutlookSendSkill)
 skill_registry.register(OutlookReadSkill)
 skill_registry.register(OutlookCalendarReadSkill)
 skill_registry.register(OutlookCalendarWriteSkill)
 skill_registry.register(OneDriveUploadSkill)
 skill_registry.register(WordCreateSkill)
 skill_registry.register(ExcelCreateSkill)
 skill_registry.register(OneNoteCreateSkill)
 skill_registry.register(OutlookContactLookupSkill)
except Exception as e:
 logger.warning(f"Failed to load Microsoft skills: {e}")

logger.info(f"Skill registry initialized: {len(skill_registry.list())} skills registered")

__all__ = [
    "skill_registry",
    "SkillRegistry",
    "BaseSkill",
]