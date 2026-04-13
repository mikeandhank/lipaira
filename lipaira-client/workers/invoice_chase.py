"""
Invoice chase background worker for Lipaira.
Automatically identifies overdue invoices from QuickBooks and sends follow-up
email reminders via Resend. Configurable grace period (days_overdue) and dry-run mode.
Triggered by the scheduler or manually via the operator layer.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

# Import QuickBooks client
try:
    from lipaira_client.skills.quickbooks_client import qb_query, get_qb_credentials
except ImportError:
    from quickbooks_client import qb_query, get_qb_credentials


def get_overdue_invoices(user_id: str, days_overdue: int = 7) -> List[Dict]:
    """
    Get invoices overdue by specified days from QuickBooks.
    """
    query = f"""
    SELECT 
        Id, DocNumber, CustomerRef, TotalAmt, Balance, 
        DueDate, CustomerRef.name, CustomerRef.email
    FROM Invoice 
    WHERE Balance > 0 
    AND DueDate < '{datetime.now().date() - timedelta(days=days_overdue)}'
    """
    
    try:
        results = qb_query(query)
        return results
    except Exception as e:
        log.error(f"Failed to query QuickBooks: {e}")
        return []


def get_customer_email(user_id: str, customer_id: str) -> Optional[str]:
    """
    Get customer email from QuickBooks.
    """
    query = f"""
    SELECT Id, PrimaryEmailAddr 
    FROM Customer 
    WHERE Id = '{customer_id}'
    """
    
    try:
        results = qb_query(query)
        if results and results[0].get('PrimaryEmailAddr'):
            return results[0]['PrimaryEmailAddr'].get('Address')
    except Exception as e:
        log.error(f"Failed to get customer email: {e}")
    
    return None


def generate_chase_email(invoice: Dict, days_overdue: int, business_name: str) -> Dict:
    """
    Generate a professional chase email for overdue invoice.
    """
    customer_name = invoice.get('CustomerRef', {}).get('name', 'Valued Customer')
    invoice_num = invoice.get('DocNumber', 'Unknown')
    amount = invoice.get('Balance', 0)
    due_date = invoice.get('DueDate', 'Unknown')
    
    # Customize message based on how overdue
    if days_overdue >= 30:
        tone = "final"
        subject = f"Final Notice: Invoice #{invoice_num} overdue {days_overdue} days"
        intro = f"This is a final reminder about an overdue invoice for {business_name}."
    elif days_overdue >= 14:
        tone = "urgent"
        subject = f"Urgent: Invoice #{invoice_num} overdue {days_overdue} days"
        intro = f"This is a friendly reminder that invoice #{invoice_num} is overdue."
    else:
        tone = "friendly"
        subject = f"Friendly reminder: Invoice #{invoice_num}"
        intro = f"Just a quick reminder about an outstanding invoice from {business_name}."
    
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <p>Hi {customer_name},</p>
        
        <p>{intro}</p>
        
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #666;">Invoice #</td>
                    <td style="text-align: right; padding: 8px 0;">{invoice_num}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;">Amount Due</td>
                    <td style="text-align: right; padding: 8px 0; font-weight: bold;">${amount:.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;">Due Date</td>
                    <td style="text-align: right; padding: 8px 0;">{due_date}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;">Days Overdue</td>
                    <td style="text-align: right; padding: 8px 0; color: #dc2626;">{days_overdue} days</td>
                </tr>
            </table>
        </div>
        
        <p>Please review and let us know if you have any questions or need to set up a payment plan.</p>
        
        <p>Thank you for your prompt attention to this matter.</p>
        
        <p>Best regards,<br/>{business_name}</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #999; font-size: 12px;">
            If you've already sent payment, please disregard this reminder.
        </p>
    </div>
    """
    
    return {
        "subject": subject,
        "html": html,
        "text": f"Hi {customer_name},\n\n{intro}\n\nInvoice #{invoice_num}\nAmount Due: ${amount:.2f}\nDue Date: {due_date}\nDays Overdue: {days_overdue}\n\nPlease contact us with any questions.\n\nBest regards,\n{business_name}"
    }


def send_chase_email(user_id: str, business_id: str, invoice: Dict, 
                     from_email: str, from_name: str, business_name: str) -> Dict:
    """
    Send invoice chase email via Resend.
    """
    from lipaira_client.skills.email_send_skill import EmailSendSkill
    
    customer_email = invoice.get('CustomerRef', {}).get('email')
    customer_id = invoice.get('CustomerRef', {}).get('value')
    
    # Try to get email from customer record if not in invoice
    if not customer_email and customer_id:
        customer_email = get_customer_email(user_id, customer_id)
    
    if not customer_email:
        return {
            "success": False,
            "error": f"No email found for customer {invoice.get('CustomerRef', {}).get('name')}"
        }
    
    # Calculate days overdue
    due_date = invoice.get('DueDate')
    if due_date:
        try:
            due = datetime.strptime(due_date, '%Y-%m-%d').date()
            days_overdue = (datetime.now().date() - due).days
        except:
            days_overdue = 7
    else:
        days_overdue = 7
    
    # Generate email content
    email = generate_chase_email(invoice, days_overdue, business_name)
    
    # Send via email skill
    skill = EmailSendSkill()
    result = skill.execute({
        "to": customer_email,
        "subject": email["subject"],
        "body": email["html"],
        "from_name": from_name
    })
    
    return {
        "success": result.success,
        "invoice_id": invoice.get('Id'),
        "customer_email": customer_email,
        "message": result.output.get("message") if result.output else None,
        "error": result.error
    }


def run_invoice_chase(user_id: str, business_id: str = None,
                      business_name: str = "Your Business",
                      from_email: str = None, from_name: str = None,
                      days_overdue: int = 7, dry_run: bool = False) -> Dict:
    """
    Main entry point for invoice chase workflow.
    
    Args:
        user_id: User identifier
        business_id: Optional business ID for multi-business users
        business_name: Name to use in email signature
        from_email: Email address to send from
        from_name: Name to send as
        days_overdue: Only chase invoices overdue by this many days
        dry_run: If True, don't actually send emails
    
    Returns:
        Dict with chase results
    """
    log.info(f"Running invoice chase for user {user_id}, overdue {days_overdue}+ days")
    
    # Get overdue invoices
    invoices = get_overdue_invoices(user_id, days_overdue)
    
    if not invoices:
        return {
            "success": True,
            "message": "No overdue invoices found",
            "invoices_found": 0,
            "emails_sent": 0
        }
    
    log.info(f"Found {len(invoices)} overdue invoices")
    
    # Default from_email if not provided
    if not from_email:
        from_email = os.environ.get("RESEND_FROM_EMAIL", "billing@lipaira.ai")
    if not from_name:
        from_name = business_name
    
    results = []
    emails_sent = 0
    
    for invoice in invoices:
        if dry_run:
            log.info(f"[DRY RUN] Would send chase for invoice {invoice.get('DocNumber')}")
            results.append({
                "invoice": invoice.get('DocNumber'),
                "customer": invoice.get('CustomerRef', {}).get('name'),
                "amount": invoice.get('Balance'),
                "dry_run": True
            })
            continue
        
        # Send chase email
        result = send_chase_email(
            user_id=user_id,
            business_id=business_id,
            invoice=invoice,
            from_email=from_email,
            from_name=from_name,
            business_name=business_name
        )
        
        results.append(result)
        
        if result.get("success"):
            emails_sent += 1
            log.info(f"Sent chase for invoice {invoice.get('DocNumber')} to {result.get('customer_email')}")
        else:
            log.error(f"Failed to send chase for invoice {invoice.get('DocNumber')}: {result.get('error')}")
    
    return {
        "success": True,
        "invoices_found": len(invoices),
        "emails_sent": emails_sent,
        "results": results
    }


if __name__ == "__main__":
    # Test run
    import sys
    user_id = sys.argv[1] if len(sys.argv) > 1 else "test-user"
    
    result = run_invoice_chase(
        user_id=user_id,
        business_name="Test Business",
        dry_run=True
    )
    print(result)