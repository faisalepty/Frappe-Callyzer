import frappe
import requests
import json
from callyzer.callyzer.utils import get_callyzer_settings
from callyzer.api.fetch_employee import parse_datetime, process_employee
from frappe import _

@frappe.whitelist()
def fetch_summary_report():
    start_date = frappe.form_dict.get("start_date")
    end_date = frappe.form_dict.get("end_date")
    company = frappe.form_dict.get("company")
    if not start_date or not end_date:
        frappe.throw(_("Start date and end date are required"))
        
    settings = get_callyzer_settings(company)
    if not settings:
        frappe.throw(_("Callyzer settings not found for the company"))
    
    url = settings.domain_api + settings.call_log + "/summary_report"
    api_key = settings.api_key

    headers = {
        "spi-key": api_key,
        "company": company,
        "Content-Type": "application/json"
    }

    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "company": company,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Failed to fetch summary report"))
        frappe.throw(_("Error fetching summary report"))

@frappe.whitelist(allow_guest=True)
def callyzer_call_log_webhook():
    """Webhook endpoint for receiving and processing Callyzer employee & call log data."""
    try:
        if frappe.request.method != "POST":
            frappe.throw(_("Webhook only accepts POST requests"), frappe.ValidationError)

        payload = frappe.request.get_json()
        if not payload:
            frappe.throw(_("Invalid or empty JSON payload"))

        data = normalize_payload(payload)

        total_created = 0
        total_logs = 0

        for item in data:
            employee_name, is_new = process_employee(item)
            if is_new:
                total_created += 1

            logs_created = process_call_logs(employee_name, item.get("call_logs", []))
            total_logs += logs_created

        return {
            "status": "success",
            "employees_created": total_created,
            "call_logs_created": total_logs
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Webhook: Failed to process Callyzer data")
        return {"status": "error", "message": "Processing failed"}


def normalize_payload(payload):
    """Normalize input payload to a list of data dictionaries."""
    if isinstance(payload, list):
        return payload
    elif isinstance(payload, dict):
        return payload.get("result", []) or [payload]
    else:
        frappe.throw(_("Unexpected payload format"))



def process_call_logs(employee_name, call_logs):
    """Create new call logs for the employee and return the number created."""
    count = 0
    for call in call_logs:
        if frappe.db.exists("Callyzer Call Log", {"external_id": call["id"]}):
            continue

        doc = frappe.new_doc("Callyzer Call Log")
        doc.employee = employee_name
        doc.call_log_id = call["id"]
        doc.client_name = call["client_name"]
        doc.client_country_code = call["client_country_code"]
        doc.client_no = call["client_number"]
        doc.duration = call["duration"]
        doc.call_type = call["call_type"]
        doc.call_date = call["call_date"]
        doc.call_time = call["call_time"]
        doc.note = json.dumps(call.get("note", ""))
        doc.call_recording_url = call["call_recording_url"]
        doc.crm_status = call.get("crm_status")
        doc.reminder_date = call.get("reminder_date")
        doc.reminder_time = call.get("reminder_time")
        doc.synced_at = parse_datetime(call.get("synced_at"))
        doc.modified_at = parse_datetime(call.get("modified_at"))

        doc.insert(ignore_permissions=True)
        count += 1

    return count
