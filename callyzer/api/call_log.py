import frappe
import requests
import json
from callyzer.callyzer.utils import get_callyzer_settings
from callyzer.api.fetch_employee import parse_datetime, process_employee
from frappe import _
import time
from datetime import datetime


@frappe.whitelist()
def fetch_summary_report():
    call_from = format_time_timestamp(datetime.strptime(frappe.form_dict.get("start_date"), "%Y-%m-%d %H:%M:%S"))
    call_to = format_time_timestamp(datetime.strptime(frappe.form_dict.get("end_date"), "%Y-%m-%d %H:%M:%S"))
    company = frappe.form_dict.get("company")
    # frappe.throw(str(call_from))
    if not call_from or not call_to:
        frappe.throw(_("Call from and call to (timestamps) are required"))

    settings = get_callyzer_settings(company)
    if not settings:
        frappe.throw(_("Callyzer settings not found for the company"))

    url = f"{settings.domain_api}/call-log/summary"
    token = settings.api_key  # assuming this is the Bearer token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    call_from_ = 1747083600

    call_to_ = 1747255612
    # frappe.throw(str(call_to))
    employee_ids = get_employees()
    
    # frappe.throw(str(employee_ids))
    payload = {
        "call_from": int(call_from_),
        "call_to": int(call_to_),
        "call_types": ["Missed", "Rejected", "Incoming", "Outgoing"],
        "emp_numbers": employee_ids,
        # "emp_numbers": ["780454763", "733511309", "733366016", "785388806", "785388805"],
        "duration_les_than": 20,
        "emp_tags": ["api"],
        "is_exclude_numbers": True
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

def get_employees():
    employees_id = []
    all_callyzer_employee = frappe.get_all("Callyzer Employee", fields=["name"])
    for employee in all_callyzer_employee:
        employees_id.append(employee.name)
    return employees_id


def format_time_timestamp(dt=None):
    """
    Convert a datetime object to Unix timestamp (seconds since epoch).
    If no datetime is provided, use the current time.
    """
    if dt is None:
        dt = datetime.now()
    return int(time.mktime(dt.timetuple()))
