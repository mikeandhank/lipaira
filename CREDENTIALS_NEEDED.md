# Lipaira - Credentials Needed

## OAuth Setup Checklist

### Google OAuth (Required for GSuite integration)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 Client ID credentials:
   - Application type: Web application
   - Name: Lipaira
   - Authorized redirect URI: `https://lipaira.ai/api/auth/google/callback`
3. Copy Client ID and Client Secret
4. Add directly to AWS Secrets Manager:
   - `lipaira/Google_OAuth_Client_ID`
   - `lipaira/Google_OAuth_Client_Secret`

### Microsoft OAuth (Required for Microsoft 365 integration)
1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. New registration:
   - Name: Lipaira
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: `https://lipaira.ai/api/auth/microsoft/callback`
3. Certificates & secrets → New client secret
4. API permissions → Microsoft Graph → Delegated → Add:
   - Mail.Send, Mail.Read
   - Calendars.ReadWrite
   - Files.ReadWrite
   - Contacts.Read
   - Notes.ReadWrite
   - offline_access
   - User.Read
5. Grant admin consent
6. Add directly to AWS Secrets Manager:
   - `lipaira/Microsoft_OAuth_Client_ID`
   - `lipaira/Microsoft_OAuth_Client_Secret`

### Resend (Email sending)
- Already configured in TOOLS.md
- Add to ASM: `lipaira/Resend_API_Key` if not already

---

**Note:** Credentials go directly to AWS Secrets Manager - never passed through Hank or stored in files.

### QuickBooks OAuth (Required for accounting integration)
1. Go to [developer.intuit.com](https://developer.intuit.com)
2. Create app → QuickBooks Online and Payments
3. Redirect URI: `https://lipaira.ai/api/auth/quickbooks/callback`
4. Get Client ID + Client Secret
5. Add directly to AWS Secrets Manager:
   - `lipaira/QuickBooks_Client_ID`
   - `lipaira/QuickBooks_Client_Secret`
6. Note: Use sandbox for testing, switch to production later
