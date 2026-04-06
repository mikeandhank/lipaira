"""
Defines available capabilities per integration,
their OAuth scopes, and display labels.
"""

CAPABILITIES = {

 # ── Google ────────────────────────────────────────────────────────────────
 "google": {
     "gmail.read": {
         "label": "Read emails",
         "description": "Agent can read your inbox and search emails",
         "scope": "https://www.googleapis.com/auth/gmail.readonly",
         "risk": "medium",
         "default": False,
     },
     "gmail.send": {
         "label": "Send emails",
         "description": "Agent can send emails on your behalf",
         "scope": "https://www.googleapis.com/auth/gmail.send",
         "risk": "medium",
         "default": True,
     },
     "calendar.read": {
         "label": "Read calendar",
         "description": "Agent can view your events and availability",
         "scope": "https://www.googleapis.com/auth/calendar.readonly",
         "risk": "low",
         "default": True,
     },
     "calendar.write": {
         "label": "Create and edit events",
         "description": "Agent can create, update, and delete calendar events",
         "scope": "https://www.googleapis.com/auth/calendar.events",
         "risk": "medium",
         "default": True,
     },
     "drive.file": {
         "label": "Save files to Drive",
         "description": "Agent can save documents it creates to your Drive",
         "scope": "https://www.googleapis.com/auth/drive.file",
         "risk": "low",
         "default": True,
     },
     "drive.read": {
         "label": "Read Drive files",
         "description": "Agent can read files you share with it",
         "scope": "https://www.googleapis.com/auth/drive.readonly",
         "risk": "medium",
         "default": False,
     },
     "contacts.read": {
         "label": "Read contacts",
         "description": "Agent can look up contact details by name",
         "scope": "https://www.googleapis.com/auth/contacts.readonly",
         "risk": "low",
         "default": True,
     },
     "business.manage": {
         "label": "Google Business Profile",
         "description": "Agent can post updates and respond to reviews",
         "scope": "https://www.googleapis.com/auth/business.manage",
         "risk": "medium",
         "default": False,
     },
     "docs.edit": {
         "label": "Create and edit Docs",
         "description": "Agent can create and modify Google Docs",
         "scope": "https://www.googleapis.com/auth/documents",
         "risk": "low",
         "default": True,
     },
     "sheets.edit": {
         "label": "Create and edit Sheets",
         "description": "Agent can create and modify Google Sheets",
         "scope": "https://www.googleapis.com/auth/spreadsheets",
         "risk": "low",
         "default": True,
     },
 },

 # ── Microsoft ─────────────────────────────────────────────────────────────
 "microsoft": {
     "outlook.read": {
         "label": "Read emails",
         "description": "Agent can read your Outlook inbox",
         "scope": "Mail.Read",
         "risk": "medium",
         "default": False,
     },
     "outlook.send": {
         "label": "Send emails",
         "description": "Agent can send emails from your Outlook account",
         "scope": "Mail.Send",
         "risk": "medium",
         "default": True,
     },
     "calendar.read": {
         "label": "Read calendar",
         "description": "Agent can view your Outlook calendar",
         "scope": "Calendars.Read",
         "risk": "low",
         "default": True,
     },
     "calendar.write": {
         "label": "Create and edit events",
         "description": "Agent can create and update Outlook calendar events",
         "scope": "Calendars.ReadWrite",
         "risk": "medium",
         "default": True,
     },
     "onedrive.write": {
         "label": "Save files to OneDrive",
         "description": "Agent can save documents to your OneDrive",
         "scope": "Files.ReadWrite",
         "risk": "low",
         "default": True,
     },
     "contacts.read": {
         "label": "Read contacts",
         "description": "Agent can look up Outlook contacts by name",
         "scope": "Contacts.Read",
         "risk": "low",
         "default": True,
     },
     "onenote.write": {
         "label": "Create OneNote pages",
         "description": "Agent can create pages in your OneNote notebooks",
         "scope": "Notes.ReadWrite",
         "risk": "low",
         "default": True,
     },
 },

 # ── Slack ─────────────────────────────────────────────────────────────────
 "slack": {
     "post.channels": {
         "label": "Post to channels",
         "description": "Agent can post messages to channels you select",
         "scope": "chat:write",
         "risk": "low",
         "default": True,
     },
     "read.selected": {
         "label": "Read selected channels",
         "description": "Agent can read messages in channels you explicitly choose",
         "scope": "channels:history",
         "risk": "medium",
         "default": False,
     },
     "dm.send": {
         "label": "Send direct messages",
         "description": "Agent can send DMs to team members",
         "scope": "im:write",
         "risk": "medium",
         "default": False,
     },
     "files.upload": {
         "label": "Upload files",
         "description": "Agent can share files and documents in Slack",
         "scope": "files:write",
         "risk": "low",
         "default": True,
     },
 },

 # ── Notion ────────────────────────────────────────────────────────────────
 "notion": {
     "pages.read": {
         "label": "Read pages",
         "description": "Agent can read Notion pages you share with it",
         "scope": "read_content",
         "risk": "low",
         "default": True,
     },
     "pages.write": {
         "label": "Create and edit pages",
         "description": "Agent can create new pages and edit existing ones",
         "scope": "update_content insert_content",
         "risk": "medium",
         "default": True,
     },
     "databases.read": {
         "label": "Read databases",
         "description": "Agent can query your Notion databases",
         "scope": "read_content",
         "risk": "low",
         "default": True,
     },
     "databases.write": {
         "label": "Add database entries",
         "description": "Agent can add and update rows in your databases",
         "scope": "update_content insert_content",
         "risk": "medium",
         "default": True,
     },
 },

 # ── Trello ────────────────────────────────────────────────────────────────
 "trello": {
     "boards.read": {
         "label": "Read boards",
         "description": "Agent can view your Trello boards and cards",
         "scope": "read",
         "risk": "low",
         "default": True,
     },
     "cards.write": {
         "label": "Create and move cards",
         "description": "Agent can create cards and move them between lists",
         "scope": "write",
         "risk": "low",
         "default": True,
     },
     "comments.write": {
         "label": "Add comments",
         "description": "Agent can add comments to cards",
         "scope": "write",
         "risk": "low",
         "default": True,
     },
 },

 # ── Asana ────────────────────────────────────────────────────────────────
 "asana": {
     "tasks.read": {
         "label": "Read tasks",
         "description": "Agent can view your tasks and projects",
         "scope": "default",
         "risk": "low",
         "default": True,
     },
     "tasks.write": {
         "label": "Create and update tasks",
         "description": "Agent can create tasks, set due dates, and mark complete",
         "scope": "default",
         "risk": "low",
         "default": True,
     },
     "projects.write": {
         "label": "Create projects",
         "description": "Agent can create new Asana projects",
         "scope": "default",
         "risk": "medium",
         "default": False,
     },
     "comments.write": {
         "label": "Add comments",
         "description": "Agent can add comments to tasks",
         "scope": "default",
         "risk": "low",
         "default": True,
     },
 },

 # ── Monday.com ────────────────────────────────────────────────────────────
 "monday": {
     "boards.read": {
         "label": "Read boards",
         "description": "Agent can view your Monday.com boards and items",
         "scope": "boards:read",
         "risk": "low",
         "default": True,
     },
     "items.write": {
         "label": "Create and update items",
         "description": "Agent can create items and update their status",
         "scope": "boards:write",
         "risk": "low",
         "default": True,
     },
     "updates.write": {
         "label": "Post updates",
         "description": "Agent can post updates on items",
         "scope": "updates:write",
         "risk": "low",
         "default": True,
     },
 },

 # ── Basecamp ──────────────────────────────────────────────────────────────
 "basecamp": {
     "projects.read": {
         "label": "Read projects",
         "description": "Agent can view your Basecamp projects and to-dos",
         "scope": "default",
         "risk": "low",
         "default": True,
     },
     "todos.write": {
         "label": "Create to-dos",
         "description": "Agent can create and complete to-do items",
         "scope": "default",
         "risk": "low",
         "default": True,
     },
     "messages.write": {
         "label": "Post messages",
         "description": "Agent can post messages to message boards",
         "scope": "default",
         "risk": "medium",
         "default": False,
     },
     "comments.write": {
         "label": "Add comments",
         "description": "Agent can comment on to-dos and messages",
         "scope": "default",
         "risk": "low",
         "default": True,
     },
 },

 # ── Square ────────────────────────────────────────────────────────────────
 "square": {
     "payments.read": {
         "label": "View payments",
         "description": "Agent can view payment history and transactions",
         "scope": "PAYMENTS_READ",
         "risk": "low",
         "default": True,
     },
     "invoices.write": {
         "label": "Create and send invoices",
         "description": "Agent can create invoices and send payment links",
         "scope": "INVOICES_WRITE",
         "risk": "medium",
         "default": True,
     },
     "customers.read": {
         "label": "Read customers",
         "description": "Agent can look up customer records",
         "scope": "CUSTOMERS_READ",
         "risk": "low",
         "default": True,
     },
     "customers.write": {
         "label": "Create and update customers",
         "description": "Agent can add new customers to your Square directory",
         "scope": "CUSTOMERS_WRITE",
         "risk": "low",
         "default": True,
     },
     "appointments.read": {
         "label": "Read appointments",
         "description": "Agent can view your Square Appointments schedule",
         "scope": "APPOINTMENTS_READ",
         "risk": "low",
         "default": True,
     },
     "appointments.write": {
         "label": "Book appointments",
         "description": "Agent can create and update appointments",
         "scope": "APPOINTMENTS_WRITE",
         "risk": "medium",
         "default": False,
     },
 },

 # ── QuickBooks ────────────────────────────────────────────────────────────
 "quickbooks": {
     "accounting.read": {
         "label": "Read financial data",
         "description": "Agent can view invoices, expenses, and reports",
         "scope": "com.intuit.quickbooks.accounting",
         "risk": "low",
         "default": True,
     },
     "accounting.write": {
         "label": "Create financial records",
         "description": "Agent can create invoices, log expenses, record payments",
         "scope": "com.intuit.quickbooks.accounting",
         "risk": "medium",
         "default": True,
     },
 },

 # ── HubSpot ───────────────────────────────────────────────────────────────
 "hubspot": {
     "contacts.read": {
         "label": "Read contacts",
         "description": "Agent can search and view CRM contacts",
         "scope": "crm.objects.contacts.read",
         "risk": "low",
         "default": True,
     },
     "contacts.write": {
         "label": "Create and update contacts",
         "description": "Agent can add new contacts and update existing ones",
         "scope": "crm.objects.contacts.write",
         "risk": "low",
         "default": True,
     },
     "deals.read": {
         "label": "Read deals",
         "description": "Agent can view your sales pipeline",
         "scope": "crm.objects.deals.read",
         "risk": "low",
         "default": True,
     },
     "deals.write": {
         "label": "Create and update deals",
         "description": "Agent can create deals and move them through the pipeline",
         "scope": "crm.objects.deals.write",
         "risk": "low",
         "default": True,
     },
     "notes.write": {
         "label": "Log notes and activities",
         "description": "Agent can log call notes and activities against contacts",
         "scope": "crm.objects.notes.write",
         "risk": "low",
         "default": True,
     },
 },
}


def get_capabilities(provider: str) -> dict:
    """Return capability definitions for a provider."""
    return CAPABILITIES.get(provider, {})


def get_default_capabilities(provider: str) -> list:
    """Return list of capability keys that are on by default."""
    caps = CAPABILITIES.get(provider, {})
    return [key for key, val in caps.items() if val.get("default")]


def get_scopes_for_capabilities(provider: str, capabilities: list) -> list:
    """
    Given a list of capability keys, return the OAuth scopes to request.
    Deduplicates scopes that appear in multiple capabilities.
    """
    caps = CAPABILITIES.get(provider, {})
    scopes = set()
    for cap in capabilities:
        if cap in caps:
            scope_str = caps[cap].get("scope", "")
            for scope in scope_str.split():
                scopes.add(scope)
    return list(scopes)


def check_permission(conn, user_id: str, provider: str, capability: str) -> bool:
    """
    Check if a user has granted a specific capability.
    Called by skills before performing sensitive operations.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT granted FROM integration_permissions
            WHERE user_id = %s AND provider = %s AND capability = %s
        """, (user_id, provider, capability))
        row = cur.fetchone()
        return bool(row and row[0])


def save_permissions(conn, user_id: str, provider: str, capabilities: list):
    """Save granted capabilities after OAuth connect."""
    with conn.cursor() as cur:
        # Clear existing
        cur.execute("""
            DELETE FROM integration_permissions
            WHERE user_id = %s AND provider = %s
        """, (user_id, provider))
        # Insert granted
        for cap in capabilities:
            cur.execute("""
                INSERT INTO integration_permissions
                (user_id, provider, capability, granted)
                VALUES (%s, %s, %s, true)
            """, (user_id, provider, cap))
        conn.commit()