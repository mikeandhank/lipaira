"""
PDF generation skills using WeasyPrint + Jinja2.
Generates professional PDFs from HTML templates.
Saves to /app/data/documents/ in the user's container.
"""
import os
import uuid
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML as WeasyHTML
from .base import BaseSkill, SkillResult

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
OUTPUT_DIR = "/app/data/documents"

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def render_pdf(template_name: str, context: dict) -> str:
    """Render an HTML template to PDF. Returns the output file path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    template = jinja_env.get_template(template_name)
    html_content = template.render(**context)
    output_filename = f"{template_name.replace('.html', '')}_{uuid.uuid4().hex[:8]}.pdf"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    WeasyHTML(string=html_content).write_pdf(output_path)
    return output_path

def parse_line_items(items: list) -> tuple:
    """Parse line items and calculate subtotal, tax, total."""
    processed = []
    subtotal = 0.0
    for item in items:
        qty = float(item.get("quantity", 1))
        rate = float(item.get("rate", 0))
        amount = qty * rate
        subtotal += amount
        processed.append({
            "description": item.get("description", ""),
            "detail": item.get("detail", ""),
            "quantity": qty,
            "rate": rate,
            "amount": amount
        })
    return processed, subtotal


# ── Invoice ──────────────────────────────────────────────────────────────────

class InvoiceCreateSkill(BaseSkill):
    name = "invoice_create"
    description = (
        "Create a professional PDF invoice for a client. "
        "Use when asked to generate, create, or send an invoice. "
        "Returns the saved file path."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "client_email": {"type": "string"},
                "client_address": {"type": "string"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "rate": {"type": "number"},
                            "detail": {"type": "string"}
                        },
                        "required": ["description", "quantity", "rate"]
                    }
                },
                "tax_rate": {"type": "number", "description": "Tax % e.g. 10"},
                "discount": {"type": "number", "description": "Discount amount in $"},
                "due_days": {"type": "integer", "default": 30},
                "notes": {"type": "string"},
                "payment_instructions": {"type": "string"},
                "status": {"type": "string", "enum": ["unpaid", "paid", "overdue"], "default": "unpaid"}
            },
            "required": ["client_name", "line_items"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            line_items, subtotal = parse_line_items(input.get("line_items", []))
            tax_rate = float(input.get("tax_rate", 0))
            tax_amount = subtotal * (tax_rate / 100) if tax_rate else 0
            discount = float(input.get("discount", 0))
            total = subtotal + tax_amount - discount
            today = datetime.now()
            due_date = today + timedelta(days=int(input.get("due_days", 30)))
            status = input.get("status", "unpaid")

            context = {
                "business_name": os.environ.get("USER_BUSINESS_NAME", "My Business"),
                "business_email": os.environ.get("USER_BUSINESS_EMAIL", ""),
                "business_phone": os.environ.get("USER_BUSINESS_PHONE", ""),
                "business_address": os.environ.get("USER_BUSINESS_ADDRESS", ""),
                "invoice_number": f"INV-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                "issue_date": today.strftime("%B %d, %Y"),
                "due_date": due_date.strftime("%B %d, %Y"),
                "status": status.upper(),
                "status_class": status,
                "client_name": input.get("client_name"),
                "client_email": input.get("client_email", ""),
                "client_address": input.get("client_address", ""),
                "line_items": line_items,
                "subtotal": subtotal,
                "tax_rate": tax_rate if tax_rate else None,
                "tax_amount": tax_amount,
                "discount": discount if discount else None,
                "total": total,
                "notes": input.get("notes", ""),
                "payment_instructions": input.get("payment_instructions", ""),
            }

            path = render_pdf("invoice.html", context)
            return SkillResult(success=True, output={
                "file_path": path,
                "filename": os.path.basename(path),
                "total": f"${total:.2f}",
                "message": f"Invoice for {input['client_name']} (${total:.2f}) saved to {path}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Quote ────────────────────────────────────────────────────────────────────

class QuoteCreateSkill(BaseSkill):
    name = "quote_create"
    description = (
        "Create a professional PDF quote or estimate for a client. "
        "Use when asked to prepare a quote, estimate, or pricing for services."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "client_email": {"type": "string"},
                "client_company": {"type": "string"},
                "scope": {"type": "string", "description": "Description of work"},
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
                "tax_rate": {"type": "number"},
                "validity_days": {"type": "integer", "default": 30},
                "terms": {"type": "string"},
                "notes": {"type": "string"}
            },
            "required": ["client_name", "line_items"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            line_items, subtotal = parse_line_items(input.get("line_items", []))
            tax_rate = float(input.get("tax_rate", 0))
            tax_amount = subtotal * (tax_rate / 100) if tax_rate else 0
            total = subtotal + tax_amount
            today = datetime.now()
            validity = int(input.get("validity_days", 30))
            valid_until = today + timedelta(days=validity)

            context = {
                "business_name": os.environ.get("USER_BUSINESS_NAME", "My Business"),
                "business_email": os.environ.get("USER_BUSINESS_EMAIL", ""),
                "business_phone": os.environ.get("USER_BUSINESS_PHONE", ""),
                "business_address": os.environ.get("USER_BUSINESS_ADDRESS", ""),
                "quote_number": f"Q-{today.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                "issue_date": today.strftime("%B %d, %Y"),
                "valid_until": valid_until.strftime("%B %d, %Y"),
                "validity_days": validity,
                "client_name": input.get("client_name"),
                "client_email": input.get("client_email", ""),
                "client_company": input.get("client_company", ""),
                "scope": input.get("scope", ""),
                "line_items": line_items,
                "subtotal": subtotal,
                "tax_rate": tax_rate if tax_rate else None,
                "tax_amount": tax_amount,
                "total": total,
                "terms": input.get("terms", ""),
                "notes": input.get("notes", ""),
            }

            path = render_pdf("quote.html", context)
            return SkillResult(success=True, output={
                "file_path": path,
                "filename": os.path.basename(path),
                "total": f"${total:.2f}",
                "message": f"Quote for {input['client_name']} (${total:.2f}) saved to {path}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Contract ─────────────────────────────────────────────────────────────────

class ContractCreateSkill(BaseSkill):
    name = "contract_create"
    description = (
        "Create a service agreement or contract PDF. "
        "Use when asked to draft a contract, agreement, or terms of service."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "client_email": {"type": "string"},
                "client_company": {"type": "string"},
                "client_address": {"type": "string"},
                "services_description": {"type": "string", "description": "What services will be provided"},
                "deliverables": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "payment_terms": {"type": "string", "description": "e.g. $2,000 due on signing, balance on completion"},
                "late_payment": {"type": "string", "description": "e.g. 1.5% monthly interest"},
                "ip_terms": {"type": "string"},
                "termination_terms": {"type": "string"},
                "additional_terms": {"type": "string"}
            },
            "required": ["client_name", "services_description", "payment_terms"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            today = datetime.now()
            context = {
                "business_name": os.environ.get("USER_BUSINESS_NAME", "My Business"),
                "business_email": os.environ.get("USER_BUSINESS_EMAIL", ""),
                "business_phone": os.environ.get("USER_BUSINESS_PHONE", ""),
                "business_address": os.environ.get("USER_BUSINESS_ADDRESS", ""),
                "issue_date": today.strftime("%B %d, %Y"),
                "client_name": input.get("client_name"),
                "client_email": input.get("client_email", ""),
                "client_company": input.get("client_company", ""),
                "client_address": input.get("client_address", ""),
                "services_description": input.get("services_description"),
                "deliverables": input.get("deliverables", ""),
                "start_date": input.get("start_date", today.strftime("%B %d, %Y")),
                "end_date": input.get("end_date", ""),
                "milestones": input.get("milestones", ""),
                "payment_terms": input.get("payment_terms"),
                "late_payment": input.get("late_payment", ""),
                "ip_terms": input.get("ip_terms", ""),
                "termination_terms": input.get("termination_terms", ""),
                "additional_terms": input.get("additional_terms", ""),
            }

            path = render_pdf("contract.html", context)
            return SkillResult(success=True, output={
                "file_path": path,
                "filename": os.path.basename(path),
                "message": f"Service agreement for {input['client_name']} saved to {path}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Proposal ─────────────────────────────────────────────────────────────────

class ProposalCreateSkill(BaseSkill):
    name = "proposal_create"
    description = (
        "Create a professional multi-page business proposal PDF. "
        "Use when asked to prepare a proposal, pitch, or detailed offer for a client."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "proposal_title": {"type": "string", "description": "e.g. 'Website Redesign Proposal'"},
                "executive_summary": {"type": "string"},
                "problem_statement": {"type": "string"},
                "solution": {"type": "string"},
                "solution_highlights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                },
                "timeline_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phase": {"type": "string"},
                            "duration": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                },
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "amount": {"type": "number"},
                            "detail": {"type": "string"}
                        },
                        "required": ["description", "amount"]
                    }
                },
                "payment_terms": {"type": "string"},
                "why_us": {"type": "string"},
                "validity_days": {"type": "integer", "default": 30}
            },
            "required": ["client_name", "proposal_title"]
        }

    def execute(self, input: dict) -> SkillResult:
        try:
            today = datetime.now()
            validity = int(input.get("validity_days", 30))
            valid_until = today + timedelta(days=validity)

            raw_items = input.get("line_items", [])
            line_items = []
            total = 0.0
            for item in raw_items:
                amount = float(item.get("amount", 0))
                total += amount
                line_items.append({
                    "description": item.get("description"),
                    "amount": amount,
                    "detail": item.get("detail", "")
                })

            context = {
                "business_name": os.environ.get("USER_BUSINESS_NAME", "My Business"),
                "business_email": os.environ.get("USER_BUSINESS_EMAIL", ""),
                "business_phone": os.environ.get("USER_BUSINESS_PHONE", ""),
                "issue_date": today.strftime("%B %d, %Y"),
                "valid_until": valid_until.strftime("%B %d, %Y"),
                "client_name": input.get("client_name"),
                "proposal_title": input.get("proposal_title"),
                "executive_summary": input.get("executive_summary", ""),
                "problem_statement": input.get("problem_statement", ""),
                "solution": input.get("solution", ""),
                "solution_highlights": input.get("solution_highlights", []),
                "timeline_items": input.get("timeline_items", []),
                "line_items": line_items,
                "total": total,
                "payment_terms": input.get("payment_terms", ""),
                "why_us": input.get("why_us", ""),
            }

            path = render_pdf("proposal.html", context)
            return SkillResult(success=True, output={
                "file_path": path,
                "filename": os.path.basename(path),
                "total": f"${total:.2f}",
                "message": f"Proposal '{input['proposal_title']}' for {input['client_name']} saved to {path}"
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


# ── Profile Setup ─────────────────────────────────────────────────────────────

class BusinessProfileSkill(BaseSkill):
    name = "business_profile_set"
    description = (
        "Save the user's business information (name, email, phone, address). "
        "This information appears on all invoices, quotes, and contracts. "
        "Ask for this on first use if not already set."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "business_name": {"type": "string"},
                "business_email": {"type": "string"},
                "business_phone": {"type": "string"},
                "business_address": {"type": "string"}
            },
            "required": ["business_name", "business_email"]
        }

    def execute(self, input: dict) -> SkillResult:
        profile_path = "/app/data/.profile"
        lines = []
        for key, env_var in [
            ("business_name", "USER_BUSINESS_NAME"),
            ("business_email", "USER_BUSINESS_EMAIL"),
            ("business_phone", "USER_BUSINESS_PHONE"),
            ("business_address", "USER_BUSINESS_ADDRESS"),
        ]:
            if input.get(key):
                lines.append(f"{env_var}={input[key]}")
                os.environ[env_var] = input[key]

        with open(profile_path, "w") as f:
            f.write("\n".join(lines))

        return SkillResult(success=True, output={
            "message": f"Business profile saved for {input['business_name']}",
            "note": "Your name and contact info will now appear on all documents."
        })