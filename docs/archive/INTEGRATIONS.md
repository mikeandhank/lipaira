# Lipaira Integration Spec

## Implementation Status

| Provider | OAuth | Skills | Secrets in ASM |
|----------|-------|--------|----------------|
| Google | ✅ | 🔲 | None needed |
| Notion | ✅ | 🔲 | None needed |
| QuickBooks | ✅ | ✅ | None needed |
| HubSpot | ✅ | 🔲 | None needed |
| Pipedrive | ✅ | 🔲 | None needed |
| Salesforce | ✅ | 🔲 | None needed |
| Zoho | ✅ | 🔲 | None needed |
| Slack | ❌ | 🔲 | Missing |
| Square | ❌ | 🔲 | Missing |
| **Zoom** | ✅ Built | ✅ Built | 🔲 Needs |
| **Calendly** | ✅ Built | ✅ Built | 🔲 Needs |
| **Meta Ads** | ✅ Built | ✅ Built | 🔲 Needs |
| Canva | ❌ | ✅ Built | 🔲 Needs |
| Trello | ❌ | ✅ Built | 🔲 Needs |
| Asana | ✅ Built | ✅ Built | 🔲 Needs |
| Google Ads | 🔲 Scope | ✅ Built | 🔲 Needs |
| Zapier | ❌ | ❌ | 🔲 Needs |
| monday.com | ❌ | ❌ | 🔲 Needs |
| Airtable | ❌ | ❌ | 🔲 Needs |
| Snowflake | ❌ | ❌ | 🔲 Needs |
| Tableau | ❌ | ❌ | 🔲 Needs |

## Overview

This document specifies all OAuth integrations for Lipaira, organized by category.

## Categories

- **Project Management**: Asana, monday.com, Trello, Zapier
- **Data/Analytics**: Airtable, Snowflake, Tableau
- **Scheduling**: Calendly
- **Design**: Canva
- **Advertising**: Google Ads, Meta Ads
- **Communication**: Zoom

---

## Integration Template

Each integration follows this pattern:

```python
@app.route('/api/auth/<provider>/connect')
def <provider>_connect():
    """Start OAuth flow."""
    # 1. Validate client_id exists in ASM
    # 2. Generate state with user_id
    # 3. Build OAuth URL
    # 4. Redirect to provider

@app.route('/api/auth/<provider>/callback')
def <provider>_callback():
    # 1. Exchange code for tokens
    # 2. Save to user_integrations
    # 3. Redirect to dashboard

@app.route('/api/auth/<provider>/status')
@require_auth
def <provider>_status():
    # Check if connected

@app.route('/api/auth/<provider>/disconnect', methods=['POST'])
@require_auth
def <provider>_disconnect():
    # Remove tokens
```

---

## 1. Zapier

**Provider Key:** `zapier`

**OAuth Details:**
- Authorization URL: `https://oauth.zapier.com/exchange`
- Token URL: `https://oauth.zapier.com/access-token`
- Scopes: `read`, `write`
- Redirect URI: `https://lipaira.ai/api/auth/zapier/callback`

**ASM Secrets:**
- `lipaira/Zapier_Client_ID`
- `lipaira/Zapier_Client_Secret`

**Features:**
- Trigger workflows
- Create zaps
- Manage connections

---

## 2. Asana

**Provider Key:** `asana`

**OAuth Details:**
- Authorization URL: `https://app.asana.com/-/oauth_authorize`
- Token URL: `https://app.asana.com/-/oauth_token`
- Scopes: `default`, `workspace`, `project`
- Redirect URI: `https://lipaira.ai/api/auth/asana/callback`

**ASM Secrets:**
- `lipaira/Asana_Client_ID`
- `lipaira/Asana_Client_Secret`

**Features:**
- Create tasks
- Manage projects
- Sync workspaces

---

## 3. monday.com

**Provider Key:** `monday`

**OAuth Details:**
- Authorization URL: `https://auth.monday.com/oauth2/authorize`
- Token URL: `https://auth.monday.com/oauth2/token`
- Scopes: `boards:read`, `boards:write`, `webhooks`
- Redirect URI: `https://lipaira.ai/api/auth/monday/callback`

**ASM Secrets:**
- `lipaira/Monday_Client_ID`
- `lipaira/Monday_Client_Secret`

**Features:**
- Manage boards
- Create items
- Webhook triggers

---

## 4. Airtable

**Provider Key:** `airtable`

**OAuth Details:**
- Authorization URL: `https://airtable.com/oauth2/v1/authorize`
- Token URL: `https://airtable.com/oauth2/v1/token`
- Scopes: `data.records:read`, `data.records:write`, `schema.bases:read`
- Redirect URI: `https://lipaira.ai/api/auth/airtable/callback`

**ASM Secrets:**
- `lipaira/Airtable_Client_ID`
- `lipaira/Airtable_Client_Secret`

**Features:**
- Read bases
- Create records
- Manage schemas

---

## 5. Calendly

**Provider Key:** `calendly`

**OAuth Details:**
- Authorization URL: `https://auth.calendly.com/oauth/authorize`
- Token URL: `https://auth.calendly.com/oauth/token`
- Scopes: `default`, `webhook_reads`, `webhook_writes`
- Redirect URI: `https://lipaira.ai/api/auth/calendly/callback`

**ASM Secrets:**
- `lipaira/Calendly_Client_ID`
- `lipaira/Calendly_Client_Secret`

**Features:**
- List scheduled events
- Create webhooks
- Manage availability

---

## 6. Canva

**Provider Key:** `canva`

**OAuth Details:**
- Authorization URL: `https://www.canva.com/api/oauth/authorize`
- Token URL: `https://api.canva.com/rest/v1/oauth/token`
- Scopes: `design:content:read`, `design:content:write`
- Redirect URI: `https://lipaira.ai/api/auth/canva/callback`

**ASM Secrets:**
- `lipaira/Canva_Client_ID`
- `lipaira/Canva_Client_Secret`

**Features:**
- List designs
- Create designs
- Export designs

---

## 7. Google Ads

**Provider Key:** `google_ads`

**OAuth Details:**
- Uses existing Google OAuth
- Additional scope: `https://www.googleapis.com/auth/adwords`
- Redirect URI: `https://lipaira.ai/api/auth/google_ads/callback`

**ASM Secrets:**
- Uses existing `lipaira/Google_OAuth_Client_ID` and `_SECRET`

**Features:**
- Manage campaigns
- View reports
- Adjust budgets

---

## 8. Meta Ads (Facebook)

**Provider Key:** `meta_ads`

**OAuth Details:**
- Authorization URL: `https://www.facebook.com/v18.0/dialog/oauth`
- Token URL: `https://graph.facebook.com/v18.0/oauth/access_token`
- Scopes: `ads_management`, `ads_read`, `business_management`
- Redirect URI: `https://lipaira.ai/api/auth/meta_ads/callback`

**ASM Secrets:**
- `lipaira/Meta_Client_ID`
- `lipaira/Meta_Client_Secret`

**Features:**
- Manage ad accounts
- Create campaigns
- View analytics

---

## 9. Tableau

**Provider Key:** `tableau`

**OAuth Details:**
- Authorization URL: `https://tableauonline.com/oauth/authorize`
- Token URL: `https://tableauonline.com/api/3.8/auth/token`
- Scopes: `views`, `workbooks`, `datasources`
- Redirect URI: `https://lipaira.ai/api/auth/tableau/callback`

**ASM Secrets:**
- `lipaira/Tableau_Client_ID`
- `lipaira/Tableau_Client_Secret`

**Features:**
- Embed views
- Query data
- Manage workbooks

---

## 10. Snowflake

**Provider Key:** `snowflake`

**OAuth Details:**
- Uses Snowflake OAuth via IdP
- Must configure Snowflake OAuth in Snowflake dashboard first
- Redirect URI: `https://lipaira.ai/api/auth/snowflake/callback`

**ASM Secrets:**
- `lipaira/Snowflake_Client_ID`
- `lipaira/Snowflake_Client_Secret`
- `lipaira/Snowflake_Account_Identifier`

**Features:**
- Query databases
- Manage warehouses
- Access schemas

---

## 11. Trello

**Provider Key:** `trello`

**OAuth Details:**
- Authorization URL: `https://trello.com/1/OAuthAuthorizeToken`
- Token URL: `https://trello.com/1/OAuth/access_token`
- Scopes: `read`, `write`, `account`
- Redirect URI: `https://lipaira.ai/api/auth/trello/callback`

**ASM Secrets:**
- `lipaira/Trello_API_Key`
- `lipaira/Trello_API_Secret`

**Features:**
- Manage boards
- Create cards
- Sync lists

---

## 12. Zoom

**Provider Key:** `zoom`

**OAuth Details:**
- Authorization URL: `https://zoom.us/oauth/authorize`
- Token URL: `https://zoom.us/oauth/token`
- Scopes: `user:read`, `meeting:write`, `recording:read`
- Redirect URI: `https://lipaira.ai/api/auth/zoom/callback`

**ASM Secrets:**
- `lipaira/Zoom_Client_ID`
- `lipaira/Zoom_Client_Secret`

**Features:**
- List meetings
- Create meetings
- Manage recordings

---

## Secrets Required Summary

```bash
# Add to AWS Secrets Manager
lipaira/Zapier_Client_ID
lipaira/Zapier_Client_Secret
lipaira/Asana_Client_ID
lipaira/Asana_Client_Secret
lipaira/Monday_Client_ID
lipaira/Monday_Client_Secret
lipaira/Airtable_Client_ID
lipaira/Airtable_Client_Secret
lipaira/Calendly_Client_ID
lipaira/Calendly_Client_Secret
lipaira/Canva_Client_ID
lipaira/Canva_Client_Secret
lipaira/Meta_Client_ID
lipaira/Meta_Client_Secret
lipaira/Tableau_Client_ID
lipaira/Tableau_Client_Secret
lipaira/Snowflake_Client_ID
lipaira/Snowflake_Client_Secret
lipaira/Snowflake_Account_Identifier
lipaira/Trello_API_Key
lipaira/Trello_API_Secret
lipaira/Zoom_Client_ID
lipaira/Zoom_Client_Secret
```

---

## Implementation Status

| Integration | Status | Notes |
|-------------|--------|-------|
| Zapier | 🔲 Not started | Needs OAuth creds |
| Asana | 🔲 Not started | Needs OAuth creds |
| monday.com | 🔲 Not started | Needs OAuth creds |
| Airtable | 🔲 Not started | Needs OAuth creds |
| Calendly | 🔲 Not started | Needs OAuth creds |
| Canva | 🔲 Not started | Needs OAuth creds |
| Google Ads | 🔲 Not started | Add scope to Google |
| Meta Ads | 🔲 Not started | Needs OAuth creds |
| Tableau | 🔲 Not started | Needs OAuth creds |
| Snowflake | 🔲 Not started | Needs OAuth creds |
| Trello | 🔲 Not started | Needs OAuth creds |
| Zoom | 🔲 Not started | Needs OAuth creds |

---

## UI Integration Points

Each integration should appear in:
1. **Sidebar** - Quick connect buttons
2. **Dashboard** - Integration cards with status
3. **Skills Registry** - As available skills for workflows

---

*Last updated: 2026-04-02*