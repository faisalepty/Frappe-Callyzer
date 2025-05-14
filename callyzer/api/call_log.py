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
 
    employee_ids = get_employees()
    
    payload = {
        "call_from": int(call_from),
        "call_to": int(call_to),
        "call_types": ["Missed", "Rejected", "Incoming", "Outgoing"],
        "emp_numbers": employee_ids,
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

def format_time_timestamp_(date):
    return int(datetime.timestamp(date))

@frappe.whitelist()
def fetch_employee_summary_report():
    # Fetch and validate parameters
    start_date = frappe.form_dict.get("start_date")
    end_date = frappe.form_dict.get("end_date")
    company = frappe.form_dict.get("company")

    if not (start_date and end_date and company):
        frappe.throw(_("Start Date, End Date and Company are required"))

    try:
        call_from = format_time_timestamp_(datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S"))
        call_to = format_time_timestamp_(datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        frappe.throw(_("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"))

    # Get API settings
    settings = get_callyzer_settings(company)
    if not settings:
        frappe.throw(_("Callyzer settings not found for the company"))

    # Prepare headers and payload
    url = f"{settings.domain_api}/call-log/employee-summary"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "call_from": call_from,
        "call_to": call_to,
        "call_types": ["Missed", "Rejected", "Incoming", "Outgoing"],
        "emp_numbers": [],
        "duration_les_than": 20,
        "emp_tags": [],
        "is_exclude_numbers": True
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        response.raise_for_status()
        employees = employees = response.json().get("result", [])


        inserted = 0
        for emp in employees:
            if not frappe.db.exists("Callyzer Employee", {"employee_no": emp.get("emp_number")}):
                process_employee(emp)

            doc = frappe.new_doc("Callyzer Employee Summary")
            doc.employee_name = emp.get("emp_name")
            doc.employee_code = emp.get("emp_code")
            doc.emp_country_code = emp.get("emp_country_code")
            doc.employee = emp.get("emp_number")
            doc.emp_tags = ", ".join(emp.get("emp_tags", []))
            doc.total_incoming_calls = emp.get("total_incoming_calls")
            doc.total_outgoing_calls = emp.get("total_outgoing_calls")
            doc.total_missed_calls = emp.get("total_missed_calls")
            doc.total_rejected_calls = emp.get("total_rejected_calls")
            doc.total_calls = emp.get("total_calls")
            doc.total_duration = emp.get("total_duration")
            doc.total_connected_calls = emp.get("total_connected_calls")
            doc.total_never_attended_calls = emp.get("total_never_attended_calls")
            doc.total_not_pickup_by_clients_calls = emp.get("total_not_pickup_by_clients_calls")
            doc.total_unique_clients = emp.get("total_unique_clients")
            doc.total_working_hours = emp.get("total_working_hours")
            doc.avg_duration_per_call = emp.get("avg_duration_per_call")
            doc.avg_incoming_duration = emp.get("avg_incoming_duration")
            doc.avg_outgoing_duration = emp.get("avg_outgoing_duration")

            doc.last_call_log = json.dumps(emp.get("last_call_log", {}))

            doc.insert(ignore_permissions=True)
            inserted += 1

        return {"status": "success", "inserted": inserted}

    except Exception:
        frappe.log_error(frappe.get_traceback(), _("Failed to fetch Callyzer summary"))
        frappe.throw(_("Could not fetch employee summary report"))
