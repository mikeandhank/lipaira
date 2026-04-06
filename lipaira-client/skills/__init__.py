"""
Lipaira Skills - Skill registry for agent actions
"""
import sys
import logging

logger = logging.getLogger(__name__)

SKILLS = {}

def _load_skills():
    """Load skills with graceful fallback for missing dependencies."""
    global SKILLS
    
    # Core skills that work without extra deps
    from .gsuite_skills import (
        GmailSendSkill, GmailReadSkill, CalendarReadSkill, CalendarWriteSkill,
        DriveUploadSkill, ContactLookupSkill, DocsCreateSkill, SheetsCreateSkill,
        SheetsAppendSkill, GoogleBusinessPostSkill, GoogleBusinessReviewsSkill, GoogleBusinessReplySkill
    )
    from .email_send_skill import EmailSendSkill
    from .calendar_skill import CalendarWriteSkill as CalWrite
    from .crm_skills import CRMContactLookupSkill, CRMContactCreateSkill, CRMDealCreateSkill, CRMDealListSkill
    from .file_skills import FileReadSkill, FileWriteSkill, FileListSkill
    from .github_skill import GitHubSkill
    from .slack_skills import SlackPostSkill, SlackReadChannelSkill, SlackDMSendSkill
    from .pm_skills import NotionCreatePageSkill, NotionSearchSkill, TrelloCardCreateSkill, AsanaTaskCreateSkill, MondayItemCreateSkill, BasecampTodoCreateSkill
    from .square_skills import SquareInvoiceCreateSkill, SquareCustomerLookupSkill, SquareAppointmentListSkill
    from .web_fetch import WebFetchSkill
    from .web_search import WebSearchSkill
    from .youtube_skills import YouTubeTranscriptSkill
    
    SKILLS.update({
        # Google/Gsuite
        'gmail_send': GmailSendSkill(),
        'gmail_read': GmailReadSkill(),
        'calendar_read': CalendarReadSkill(),
        'calendar_write': CalendarWriteSkill(),
        'drive_upload': DriveUploadSkill(),
        'contact_lookup': ContactLookupSkill(),
        'docs_create': DocsCreateSkill(),
        'sheets_create': SheetsCreateSkill(),
        'sheets_append': SheetsAppendSkill(),
        'google_business_post': GoogleBusinessPostSkill(),
        'google_business_reviews': GoogleBusinessReviewsSkill(),
        'google_business_reply': GoogleBusinessReplySkill(),
        # Other
        'email_send': EmailSendSkill(),
        'file_read': FileReadSkill(),
        'file_write': FileWriteSkill(),
        'file_list': FileListSkill(),
        'github': GitHubSkill(),
        'web_search': WebSearchSkill(),
        'web_fetch': WebFetchSkill(),
        'youtube_transcript': YouTubeTranscriptSkill(),
        # CRM
        'crm_contact_lookup': CRMContactLookupSkill(),
        'crm_contact_create': CRMContactCreateSkill(),
        'crm_deal_create': CRMDealCreateSkill(),
        'crm_deal_list': CRMDealListSkill(),
        # Slack
        'slack_post': SlackPostSkill(),
        'slack_read_channel': SlackReadChannelSkill(),
        'slack_dm_send': SlackDMSendSkill(),
        # PM
        'notion_create_page': NotionCreatePageSkill(),
        'notion_search': NotionSearchSkill(),
        'trello_card_create': TrelloCardCreateSkill(),
        'asana_task_create': AsanaTaskCreateSkill(),
        'monday_item_create': MondayItemCreateSkill(),
        'basecamp_todo_create': BasecampTodoCreateSkill(),
        # Square
        'square_invoice_create': SquareInvoiceCreateSkill(),
        'square_customer_lookup': SquareCustomerLookupSkill(),
        'square_appointment_list': SquareAppointmentListSkill(),
    })
    
    # PDF skills need weasyprint + system libs
    # Skipping for now to avoid dependency hell
    
def get_tool_definitions():
    if not SKILLS:
        _load_skills()
    return [{"name": s.name, "description": s.description, "input_schema": s.get_input_schema()} for s in SKILLS.values()]

def execute_skill(name, input):
    if not SKILLS:
        _load_skills()
    if name not in SKILLS:
        return {"success": False, "error": f"Unknown skill: {name}"}
    try:
        result = SKILLS[name].execute(input)
        return result.dict() if hasattr(result, 'dict') else {"success": True, "output": result}
    except Exception as e:
        logger.error(f"Skill {name} failed: {e}")
        return {"success": False, "error": str(e)}

# Load on import
_load_skills()


# Load additional skill modules
def _load_more_skills():
    """Load additional skill modules."""
    try:
        from .microsoft_skills import (
            OutlookSendSkill, OutlookReadSkill, OutlookCalendarReadSkill,
            OutlookCalendarWriteSkill, OneDriveUploadSkill, WordCreateSkill,
            ExcelCreateSkill, OneNoteCreateSkill, OutlookContactLookupSkill
        )
        from .quickbooks_skills import (
            QBInvoiceCreateSkill, QBEstimateCreateSkill, QBCustomerSyncSkill,
            QBCustomerListSkill, QBExpenseLogSkill, QBPaymentRecordSkill,
            QBReportProfitLossSkill, QBOutstandingInvoicesSkill
        )
        from .other_skills import CodeRunSkill, EmailDraftSkill
        
        SKILLS.update({
            # Microsoft
            'outlook_send': OutlookSendSkill(),
            'outlook_read': OutlookReadSkill(),
            'outlook_calendar_read': OutlookCalendarReadSkill(),
            'outlook_calendar_write': OutlookCalendarWriteSkill(),
            'onedrive_upload': OneDriveUploadSkill(),
            'word_create': WordCreateSkill(),
            'excel_create': ExcelCreateSkill(),
            'onenote_create': OneNoteCreateSkill(),
            'outlook_contact_lookup': OutlookContactLookupSkill(),
            # QuickBooks
            'qb_invoice_create': QBInvoiceCreateSkill(),
            'qb_estimate_create': QBEstimateCreateSkill(),
            'qb_customer_sync': QBCustomerSyncSkill(),
            'qb_customer_list': QBCustomerListSkill(),
            'qb_expense_log': QBExpenseLogSkill(),
            'qb_payment_record': QBPaymentRecordSkill(),
            'qb_report_profit_loss': QBReportProfitLossSkill(),
            'qb_outstanding_invoices': QBOutstandingInvoicesSkill(),
            # Other
            'code_run': CodeRunSkill(),
            'email_draft': EmailDraftSkill(),
        })
    except ImportError as e:
        logger.warning(f"Additional skills not loaded: {e}")

# Load more skills
_load_more_skills()
