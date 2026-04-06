"""
QuickBooks Online skills.
"""
import os
from datetime import datetime, timedelta

from .base import BaseSkill, SkillResult
from .quickbooks_client import qb_get, qb_post, qb_query


def find_or_create_customer(name: str, email: str = "") -> dict:
    escaped = name.replace("'", "\\'")
    results = qb_query(f"SELECT * FROM Customer WHERE DisplayName = '{escaped}' MAXRESULTS 1")
    if results:
        return results[0]
    
    body = {"DisplayName": name}
    if email:
        body["PrimaryEmailAddr"] = {"Address": email}
    
    result = qb_post("/customer", body)
    return result.get("Customer", {})


def get_default_income_account() -> str:
    accounts = qb_query("SELECT * FROM Account WHERE AccountType = 'Income' MAXRESULTS 1")
    return accounts[0]["Id"] if accounts else "1"


class QBInvoiceCreateSkill(BaseSkill):
    name = "qb_invoice_create"
    description = "Create an invoice in QuickBooks Online. Auto-creates customer if needed."

    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "customer_email": {"type": "string"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "rate": {"type": "number"}
                        },
                        "required": ["description", "quantity", "rate"]
                    }
                },
                "due_days": {"type": "integer", "default": 30},
                "send_email": {"type": "boolean", "default": False}
            },
            "required": ["customer_name", "line_items"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            customer = find_or_create_customer(input["customer_name"], input.get("customer_email", ""))
            account_id = get_default_income_account()
            due_date = (datetime.now() + timedelta(days=input.get("due_days", 30))).strftime("%Y-%m-%d")

            line_items = []
            for item in input["line_items"]:
                qty = float(item["quantity"])
                rate = float(item["rate"])
                line_items.append({
                    "Amount": qty * rate,
                    "DetailType": "SalesItemLineDetail",
                    "Description": item["description"],
                    "SalesItemLineDetail": {"Qty": qty, "UnitPrice": rate, "ItemAccountRef": {"value": account_id}}
                })

            invoice_body = {
                "CustomerRef": {"value": customer["Id"]},
                "DueDate": due_date,
                "Line": line_items,
            }

            result = qb_post("/invoice", invoice_body)
            invoice = result.get("Invoice", {})
            total = invoice.get("TotalAmt", 0)
            inv_id = invoice.get("Id")
            inv_num = invoice.get("DocNumber", inv_id)

            return SkillResult(success=True, output={
                "invoice_id": inv_id,
                "invoice_number": inv_num,
                "customer": input["customer_name"],
                "total": f"${total:.2f}",
                "due_date": due_date,
                "message": f"Invoice #{inv_num} created for {input['customer_name']} (${total:.2f})"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBEstimateCreateSkill(BaseSkill):
    name = "qb_estimate_create"
    description = "Create an estimate/quote in QuickBooks Online."

    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "customer_email": {"type": "string"},
                "line_items": {"type": "array", "items": {"type": "object", "properties": {"description": {"type": "string"}, "quantity": {"type": "number"}, "rate": {"type": "number"}}, "required": ["description", "quantity", "rate"]}},
                "expiry_days": {"type": "integer", "default": 30}
            },
            "required": ["customer_name", "line_items"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            customer = find_or_create_customer(input["customer_name"], input.get("customer_email", ""))
            account_id = get_default_income_account()
            expiry = (datetime.now() + timedelta(days=input.get("expiry_days", 30))).strftime("%Y-%m-%d")

            line_items = []
            for item in input["line_items"]:
                qty = float(item["quantity"])
                rate = float(item["rate"])
                line_items.append({
                    "Amount": qty * rate,
                    "DetailType": "SalesItemLineDetail",
                    "Description": item["description"],
                    "SalesItemLineDetail": {"Qty": qty, "UnitPrice": rate, "ItemAccountRef": {"value": account_id}}
                })

            body = {"CustomerRef": {"value": customer["Id"]}, "ExpirationDate": expiry, "Line": line_items}
            result = qb_post("/estimate", body)
            estimate = result.get("Estimate", {})
            total = estimate.get("TotalAmt", 0)

            return SkillResult(success=True, output={
                "estimate_id": estimate.get("Id"),
                "customer": input["customer_name"],
                "total": f"${total:.2f}",
                "expires": expiry,
                "message": f"Estimate created for {input['customer_name']} (${total:.2f})"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBCustomerSyncSkill(BaseSkill):
    name = "qb_customer_sync"
    description = "Find or create a customer in QuickBooks."

    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}}, "required": ["name"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            escaped = input["name"].replace("'", "\\'")
            results = qb_query(f"SELECT * FROM Customer WHERE DisplayName = '{escaped}' MAXRESULTS 1")
            existed = bool(results)

            if results:
                customer = results[0]
            else:
                body = {"DisplayName": input["name"]}
                if input.get("email"):
                    body["PrimaryEmailAddr"] = {"Address": input["email"]}
                result = qb_post("/customer", body)
                customer = result.get("Customer", {})

            return SkillResult(success=True, output={
                "customer_id": customer.get("Id"),
                "name": customer.get("DisplayName"),
                "existed": existed,
                "message": f"Found existing customer: {input['name']}" if existed else f"Created new customer: {input['name']}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBCustomerListSkill(BaseSkill):
    name = "qb_customer_list"
    description = "List customers from QuickBooks."

    def get_input_schema(self):
        return {"type": "object", "properties": {"search": {"type": "string"}, "max_results": {"type": "integer", "default": 20}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            max_r = min(input.get("max_results", 20), 100)
            search = input.get("search", "")
            
            if search:
                escaped = search.replace("'", "\\'")
                sql = f"SELECT * FROM Customer WHERE DisplayName LIKE '%{escaped}%' MAXRESULTS {max_r}"
            else:
                sql = f"SELECT * FROM Customer WHERE Active = true ORDERBY DisplayName MAXRESULTS {max_r}"

            customers = qb_query(sql)
            return SkillResult(success=True, output=[{"id": c.get("Id"), "name": c.get("DisplayName"), "email": c.get("PrimaryEmailAddr", {}).get("Address", ""), "balance": c.get("Balance", 0)} for c in customers])
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBExpenseLogSkill(BaseSkill):
    name = "qb_expense_log"
    description = "Log a business expense in QuickBooks."

    def get_input_schema(self):
        return {"type": "object", "properties": {"amount": {"type": "number"}, "description": {"type": "string"}, "category": {"type": "string"}, "date": {"type": "string"}, "vendor": {"type": "string"}}, "required": ["amount", "description", "category"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            category = input.get("category", "Other")
            accounts = qb_query(f"SELECT * FROM Account WHERE AccountType = 'Expense' AND Name LIKE '%{category}%' MAXRESULTS 1")
            if not accounts:
                accounts = qb_query("SELECT * FROM Account WHERE AccountType = 'Expense' MAXRESULTS 1")
            account_id = accounts[0]["Id"] if accounts else "7"

            date = input.get("date", datetime.now().strftime("%Y-%m-%d"))

            purchase_body = {
                "PaymentType": "Cash",
                "AccountRef": {"value": account_id},
                "TxnDate": date,
                "Line": [{"Amount": float(input["amount"]), "DetailType": "AccountBasedExpenseLineDetail", "Description": input["description"], "AccountBasedExpenseLineDetail": {"AccountRef": {"value": account_id}}}]
            }

            result = qb_post("/purchase", purchase_body)
            purchase = result.get("Purchase", {})

            return SkillResult(success=True, output={
                "expense_id": purchase.get("Id"),
                "amount": f"${float(input['amount']):.2f}",
                "category": category,
                "date": date,
                "message": f"Logged ${float(input['amount']):.2f} expense ({category}) for {date}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBPaymentRecordSkill(BaseSkill):
    name = "qb_payment_record"
    description = "Record a payment received from a customer."

    def get_input_schema(self):
        return {"type": "object", "properties": {"customer_name": {"type": "string"}, "amount": {"type": "number"}, "invoice_number": {"type": "string"}, "date": {"type": "string"}}, "required": ["customer_name", "amount"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            escaped = input["customer_name"].replace("'", "\\'")
            customers = qb_query(f"SELECT * FROM Customer WHERE DisplayName = '{escaped}' MAXRESULTS 1")
            if not customers:
                return SkillResult(success=False, output=None, error=f"Customer not found: {input['customer_name']}")

            customer_id = customers[0]["Id"]
            date = input.get("date", datetime.now().strftime("%Y-%m-%d"))
            amount = float(input["amount"])

            payment_body = {"CustomerRef": {"value": customer_id}, "TotalAmt": amount, "TxnDate": date}

            result = qb_post("/payment", payment_body)
            payment = result.get("Payment", {})

            return SkillResult(success=True, output={
                "payment_id": payment.get("Id"),
                "customer": input["customer_name"],
                "amount": f"${amount:.2f}",
                "date": date,
                "message": f"Recorded ${amount:.2f} payment from {input['customer_name']}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBReportProfitLossSkill(BaseSkill):
    name = "qb_report_profit_loss"
    description = "Pull Profit & Loss report from QuickBooks."

    def get_input_schema(self):
        return {"type": "object", "properties": {"period": {"type": "string", "enum": ["this_month", "last_month", "this_quarter", "this_year"], "default": "this_month"}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            period = input.get("period", "this_month")
            today = datetime.now()

            date_ranges = {
                "this_month": (today.replace(day=1), today),
                "last_month": ((today.replace(day=1) - timedelta(days=1)).replace(day=1), today.replace(day=1) - timedelta(days=1)),
                "this_quarter": (datetime(today.year, ((today.month - 1) // 3) * 3 + 1, 1), today),
                "this_year": (datetime(today.year, 1, 1), today),
            }

            start, end = date_ranges.get(period, date_ranges["this_month"])
            creds = __import__('skills.quickbooks_client', fromlist=['get_qb_credentials']).get_qb_credentials()

            import requests as req
            resp = req.get(
                f"{creds['base_url']}/v3/company/{creds['realm_id']}/reports/ProfitAndLoss",
                headers={'Authorization': f"Bearer {creds['access_token']}", 'Accept': 'application/json'},
                params={'start_date': start.strftime("%Y-%m-%d"), 'end_date': end.strftime("%Y-%m-%d"), 'minorversion': '65'},
                timeout=30
            )
            resp.raise_for_status()
            report = resp.json()

            return SkillResult(success=True, output={
                "period": period,
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "message": f"P&L report for {period}: See detailed report"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class QBOutstandingInvoicesSkill(BaseSkill):
    name = "qb_outstanding_invoices"
    description = "List all unpaid invoices from QuickBooks."

    def get_input_schema(self):
        return {"type": "object", "properties": {"max_results": {"type": "integer", "default": 20}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            max_r = min(input.get("max_results", 20), 100)
            invoices = qb_query(f"SELECT * FROM Invoice WHERE Balance > '0' ORDERBY DueDate MAXRESULTS {max_r}")

            total_outstanding = 0
            result_list = []
            today = datetime.now().date()

            for inv in invoices:
                balance = float(inv.get("Balance", 0))
                due_str = inv.get("DueDate", "")
                overdue = False
                if due_str:
                    try:
                        due_date = datetime.strptime(due_str, "%Y-%m-%d").date()
                        overdue = due_date < today
                    except ValueError:
                        pass

                total_outstanding += balance
                result_list.append({
                    "invoice_number": inv.get("DocNumber"),
                    "customer": inv.get("CustomerRef", {}).get("name", ""),
                    "balance": f"${balance:,.2f}",
                    "due_date": due_str,
                    "overdue": overdue
                })

            overdue_count = sum(1 for i in result_list if i["overdue"])

            return SkillResult(success=True, output={
                "invoices": result_list,
                "total_outstanding": f"${total_outstanding:,.2f}",
                "count": len(result_list),
                "overdue_count": overdue_count,
                "message": f"{len(result_list)} unpaid invoices totalling ${total_outstanding:,.2f} ({overdue_count} overdue)"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))