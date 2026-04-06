"""
10 GSuite skills covering Gmail, Calendar, Drive, Contacts, Docs, Sheets.
All use the shared google_client helper.
"""
import os
import base64
import json
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from .base import BaseSkill, SkillResult
from .google_client import build_service, get_credentials

# ── Gmail: Send ─────────────────────────────────────────────────────────────

class GmailSendSkill(BaseSkill):
    name = "gmail_send"
    description = (
        "Send an email from the user's Gmail account. "
        "Use for sending invoices, quotes, follow-ups, and client communications."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Email body (plain text or HTML)"},
                "cc": {"type": "string", "description": "CC email (optional)"}
            },
            "required": ["to", "subject", "body"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('gmail', 'v1')
            
            msg = MIMEMultipart()
            msg['To'] = input['to']
            msg['Subject'] = input['subject']
            if input.get('cc'):
                msg['Cc'] = input['cc']
            
            is_html = '<' in input['body']
            msg.attach(MIMEText(input['body'], 'html' if is_html else 'plain'))
            
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            return SkillResult(success=True, output={
                "message": f"Email sent to {input['to']}",
                "subject": input['subject']
            })
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Gmail: Read ─────────────────────────────────────────────────────────────

class GmailReadSkill(BaseSkill):
    name = "gmail_read"
    description = "Read recent emails from the user's Gmail inbox."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 5},
                "query": {"type": "string", "description": "Gmail search query"},
                "unread_only": {"type": "boolean", "default": False}
            }
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('gmail', 'v1')
            max_results = min(input.get('max_results', 5), 20)
            query = input.get('query', '')
            if input.get('unread_only'):
                query = f"is:unread {query}".strip()
            
            result = service.users().messages().list(
                userId='me', maxResults=max_results, q=query
            ).execute()
            
            messages = result.get('messages', [])
            emails = []
            
            for msg_ref in messages:
                msg = service.users().messages().get(
                    userId='me', id=msg_ref['id'],
                    format='metadata', metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in msg['payload']['headers']}
                emails.append({
                    'from': headers.get('From', ''),
                    'subject': headers.get('Subject', ''),
                    'date': headers.get('Date', ''),
                    'snippet': msg.get('snippet', ''),
                    'unread': 'UNREAD' in msg.get('labelIds', [])
                })
            
            return SkillResult(success=True, output=emails)
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Calendar: Read ───────────────────────────────────────────────────────────

class CalendarReadSkill(BaseSkill):
    name = "calendar_read"
    description = "Read upcoming events from the user's Google Calendar."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7},
                "max_results": {"type": "integer", "default": 10}
            }
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('calendar', 'v3')
            now = datetime.utcnow()
            end = now + timedelta(days=input.get('days_ahead', 7))
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                timeMax=end.isoformat() + 'Z',
                maxResults=min(input.get('max_results', 10), 25),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = []
            for e in events_result.get('items', []):
                start = e['start'].get('dateTime', e['start'].get('date'))
                end_t = e['end'].get('dateTime', e['end'].get('date'))
                events.append({
                    'title': e.get('summary', 'Untitled'),
                    'start': start,
                    'end': end_t,
                    'location': e.get('location', '')
                })
            
            return SkillResult(success=True, output={'events': events, 'count': len(events)})
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Calendar: Write ──────────────────────────────────────────────────────────

class CalendarWriteSkill(BaseSkill):
    name = "calendar_write"
    description = "Create a calendar event and invite attendees."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 datetime"},
                "end": {"type": "string", "description": "ISO 8601 datetime"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "add_meet": {"type": "boolean", "default": False}
            },
            "required": ["title", "start", "end"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('calendar', 'v3')
            
            event = {
                'summary': input['title'],
                'description': input.get('description', ''),
                'location': input.get('location', ''),
                'start': {'dateTime': input['start'], 'timeZone': 'UTC'},
                'end': {'dateTime': input['end'], 'timeZone': 'UTC'},
            }
            
            if input.get('attendees'):
                event['attendees'] = [{'email': e} for e in input['attendees']]
            
            if input.get('add_meet'):
                event['conferenceData'] = {'createRequest': {'requestId': f"lipaira-{datetime.now().timestamp()}"}}
            
            created = service.events().insert(
                calendarId='primary', body=event, sendUpdates='all',
                conferenceDataVersion=1 if input.get('add_meet') else 0
            ).execute()
            
            return SkillResult(success=True, output={
                'event_id': created['id'],
                'title': created.get('summary'),
                'link': created.get('htmlLink'),
                'meet_link': created.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri', ''),
                'message': f"Event created. Invites sent."
            })
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Google Drive ─────────────────────────────────────────────────────────────

class DriveUploadSkill(BaseSkill):
    name = "drive_upload"
    description = "Upload a file to Google Drive."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "folder_name": {"type": "string", "default": "Lipaira Documents"},
                "share_with": {"type": "string"}
            },
            "required": ["filename"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            from googleapiclient.http import MediaFileUpload
            drive_service = build_service('drive', 'v3')
            local_path = f"/app/data/documents/{input['filename']}"
            
            if not os.path.exists(local_path):
                return SkillResult(success=False, output=None, error=f"File not found: {input['filename']}")
            
            # Find or create folder
            folder_name = input.get('folder_name', 'Lipaira Documents')
            folders = drive_service.files().list(
                q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            ).execute()
            
            folder_id = None
            if folders.get('files'):
                folder_id = folders['files'][0]['id']
            else:
                folder = drive_service.files().create(
                    body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
                    fields='id'
                ).execute()
                folder_id = folder['id']
            
            # Upload file
            file_meta = {'name': input['filename'], 'parents': [folder_id]}
            media = MediaFileUpload(local_path, mimetype='application/pdf')
            uploaded = drive_service.files().create(
                body=file_meta, media_body=media, fields='id,webViewLink'
            ).execute()
            
            if input.get('share_with'):
                drive_service.permissions().create(
                    fileId=uploaded['id'],
                    body={'type': 'user', 'role': 'reader', 'emailAddress': input['share_with']}
                ).execute()
            
            return SkillResult(success=True, output={
                'link': uploaded.get('webViewLink'),
                'message': f"Uploaded to Drive"
            })
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Google Contacts ──────────────────────────────────────────────────────────

class ContactLookupSkill(BaseSkill):
    name = "contact_lookup"
    description = "Look up a contact from Google Contacts by name."
    
    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('people', 'v1')
            results = service.people().searchContacts(
                query=input['name'],
                readMask='names,emailAddresses,phoneNumbers',
                pageSize=5
            ).execute()
            
            contacts = []
            for result in results.get('results', []):
                person = result.get('person', {})
                names = person.get('names', [{}])
                emails = person.get('emailAddresses', [])
                phones = person.get('phoneNumbers', [])
                contacts.append({
                    'name': names[0].get('displayName', '') if names else '',
                    'email': emails[0].get('value', '') if emails else '',
                    'phone': phones[0].get('value', '') if phones else ''
                })
            
            return SkillResult(success=True, output=contacts)
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Google Docs ──────────────────────────────────────────────────────────────

class DocsCreateSkill(BaseSkill):
    name = "docs_create"
    description = "Create a Google Doc with content."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "share_with": {"type": "string"}
            },
            "required": ["title", "content"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            docs_service = build_service('docs', 'v1')
            drive_service = build_service('drive', 'v3')
            
            doc = docs_service.documents().create(body={'title': input['title']}).execute()
            doc_id = doc['documentId']
            
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': [{'insertText': {'location': {'index': 1}, 'text': input['content']}}]}
            ).execute()
            
            if input.get('share_with'):
                drive_service.permissions().create(
                    fileId=doc_id,
                    body={'type': 'user', 'role': 'writer', 'emailAddress': input['share_with']}
                ).execute()
            
            return SkillResult(success=True, output={
                'link': f"https://docs.google.com/document/d/{doc_id}/edit",
                'message': f"Google Doc created"
            })
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Google Sheets ───────────────────────────────────────────────────────────

class SheetsCreateSkill(BaseSkill):
    name = "sheets_create"
    description = "Create a Google Sheet with headers and data."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "headers": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {"type": "array"}},
                "share_with": {"type": "string"}
            },
            "required": ["title", "headers"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            sheets_service = build_service('sheets', 'v4')
            drive_service = build_service('drive', 'v3')
            
            sheet = sheets_service.spreadsheets().create(
                body={'properties': {'title': input['title']}}
            ).execute()
            sheet_id = sheet['spreadsheetId']
            
            all_rows = [input['headers']] + (input.get('rows') or [])
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range='Sheet1!A1',
                valueInputOption='USER_ENTERED', body={'values': all_rows}
            ).execute()
            
            if input.get('share_with'):
                drive_service.permissions().create(
                    fileId=sheet_id,
                    body={'type': 'user', 'role': 'writer', 'emailAddress': input['share_with']}
                ).execute()
            
            return SkillResult(success=True, output={
                'link': f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
                'message': f"Spreadsheet created"
            })
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class SheetsAppendSkill(BaseSkill):
    name = "sheets_append"
    description = "Append rows to an existing Google Sheet."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "sheet_url": {"type": "string"},
                "rows": {"type": "array", "items": {"type": "array"}}
            },
            "required": ["sheet_url", "rows"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        try:
            service = build_service('sheets', 'v4')
            match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', input['sheet_url'])
            if not match:
                return SkillResult(success=False, output=None, error="Invalid Google Sheets URL")
            
            sheet_id = match.group(1)
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id, range='Sheet1',
                valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS',
                body={'values': input['rows']}
            ).execute()
            
            return SkillResult(success=True, output={
                'message': f"Added {len(input['rows'])} row(s)"
            })
        except RuntimeError as e:
            return SkillResult(success=False, output=None, error=str(e))
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))

# Google Business Profile skills
class GoogleBusinessPostSkill(BaseSkill):
    name = "gbp_post_update"
    description = "Post an update to Google Business Profile."

    def get_input_schema(self):
        return {"type": "object", "properties": {"text": {"type": "string"}, "call_to_action": {"type": "string", "enum": ["BOOK", "ORDER", "SHOP", "LEARN_MORE", "SIGN_UP", "CALL", "none"], "default": "none"}, "cta_url": {"type": "string"}}, "required": ["text"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            from .google_client import get_credentials
            creds = get_credentials()
            
            import requests as req
            # Get account
            accounts = req.get("https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
                              headers={"Authorization": f"Bearer {creds.token}"}).json()
            account_name = accounts.get("accounts", [{}])[0].get("name")
            if not account_name:
                return SkillResult(success=False, output=None, error="No Google Business Profile found")
            
            # Get location
            locations = req.get(f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations",
                               headers={"Authorization": f"Bearer {creds.token}"}).json()
            location_name = locations.get("locations", [{}])[0].get("name")
            if not location_name:
                return SkillResult(success=False, output=None, error="No business location found")
            
            post_body = {"languageCode": "en-US", "summary": input["text"][:1500], "topicType": "STANDARD"}
            if input.get("call_to_action") != "none" and input.get("cta_url"):
                post_body["callToAction"] = {"actionType": input["call_to_action"], "url": input["cta_url"]}
            
            result = req.post(f"https://mybusiness.googleapis.com/v4/{location_name}/localPosts",
                             headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                             json=post_body).json()
            
            return SkillResult(success=True, output={"post_name": result.get("name"), "message": "Posted to Google Business Profile"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class GoogleBusinessReviewsSkill(BaseSkill):
    name = "gbp_reviews_list"
    description = "Read recent Google Business Profile reviews."

    def get_input_schema(self):
        return {"type": "object", "properties": {"max_results": {"type": "integer", "default": 10}, "unanswered_only": {"type": "boolean", "default": False}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            from .google_client import get_credentials
            creds = get_credentials()
            
            import requests as req
            accounts = req.get("https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
                              headers={"Authorization": f"Bearer {creds.token}"}).json()
            account_name = accounts.get("accounts", [{}])[0].get("name")
            locations = req.get(f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations",
                               headers={"Authorization": f"Bearer {creds.token}"}).json()
            location_name = locations.get("locations", [{}])[0].get("name")
            
            reviews = req.get(f"https://mybusiness.googleapis.com/v4/{location_name}/reviews",
                             headers={"Authorization": f"Bearer {creds.token}"},
                             params={"pageSize": input.get("max_results", 10)}).json()
            
            result = []
            for r in reviews.get("reviews", []):
                if input.get("unanswered_only") and r.get("reviewReply"):
                    continue
                result.append({"reviewer": r.get("reviewer", {}).get("displayName"), "rating": r.get("starRating"),
                              "text": r.get("comment", ""), "date": r.get("createTime", ""),
                              "replied": bool(r.get("reviewReply")), "review_id": r.get("reviewId")})
            
            return SkillResult(success=True, output=result)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class GoogleBusinessReplySkill(BaseSkill):
    name = "gbp_review_reply"
    description = "Reply to a Google Business Profile review."

    def get_input_schema(self):
        return {"type": "object", "properties": {"review_id": {"type": "string"}, "reply": {"type": "string"}}, "required": ["review_id", "reply"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            from .google_client import get_credentials
            creds = get_credentials()
            
            import requests as req
            accounts = req.get("https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
                              headers={"Authorization": f"Bearer {creds.token}"}).json()
            account_name = accounts.get("accounts", [{}])[0].get("name")
            locations = req.get(f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations",
                               headers={"Authorization": f"Bearer {creds.token}"}).json()
            location_name = locations.get("locations", [{}])[0].get("name")
            
            req.put(f"https://mybusiness.googleapis.com/v4/{location_name}/reviews/{input['review_id']}/reply",
                   headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                   json={"comment": input["reply"]}).raise_for_status()
            
            return SkillResult(success=True, output={"message": "Reply posted to Google review"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
