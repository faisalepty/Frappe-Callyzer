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


#Fetch analysis report
@frappe.whitelist()
def fetch_analysis_report():
    start_date = frappe.form_dict.get("start_date")
    end_date = frappe.form_dict.get("end_date")
    company = frappe.form_dict.get("company")

    if not (start_date and end_date and company):
        frappe.throw(_("Start Date, End Date, and Company are required"))

    try:
        call_from = int(datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").timestamp())
        call_to = int(datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").timestamp())
    except Exception:
        frappe.throw(_("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"))

    settings = get_callyzer_settings(company)
    if not settings:
        frappe.throw(_("Callyzer settings not found for the company"))

    url = f"{settings.domain_api}/call-log/analysis"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "call_from": call_from,
        "call_to": call_to,
        "call_types": ["Missed", "Rejected", "Incoming", "Outgoing"],
        "is_exclude_numbers": True
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        response.raise_for_status()

        result = response.json().get("result", {})
        if not result:
            frappe.throw(_("No analysis data found in response"))

        doc = frappe.new_doc("Callyzer Analysis")
        doc.start_date = start_date
        doc.end_date = end_date
        doc.company = company

        # Average Duration
        avg = result.get("average_duration", {})
        doc.total_duration = avg.get("total_duration")
        doc.avg_per_call = avg.get("per_call")
        doc.total_calls = avg.get("total_calls")
        doc.avg_per_day = avg.get("per_day")
        doc.total_days = avg.get("total_days")
        doc.avg_per_incoming = avg.get("per_incoming_call")
        doc.total_incoming_calls = avg.get("total_incoming_calls")
        doc.avg_per_outgoing = avg.get("per_outgoing_call")
        doc.total_outgoing_calls = avg.get("total_outgoing_calls")

        # Top Dialer
        dialer = result.get("top_dialer", {})
        doc.top_dialer_name = dialer.get("emp_name")
        doc.top_dialer_number = dialer.get("emp_number")
        doc.top_dialer_tags = ", ".join(dialer.get("emp_tags", []))
        doc.top_dialer_outgoing_calls = dialer.get("total_outgoing_calls")

        # Top Answered
        answered = result.get("top_answered", {})
        doc.top_answered_name = answered.get("emp_name")
        doc.top_answered_number = answered.get("emp_number")
        doc.top_answered_tags = ", ".join(answered.get("emp_tags", []))
        doc.top_answered_incoming_calls = answered.get("total_incoming_calls")

        # Top Caller
        caller = result.get("top_caller", {})
        doc.top_caller_name = caller.get("emp_name")
        doc.top_caller_number = caller.get("emp_number")
        doc.top_caller_tags = ", ".join(caller.get("emp_tags", []))
        doc.top_caller_total_calls = caller.get("total_calls")

        # Longest Duration
        long_dur = result.get("longest_duration", {})
        doc.longest_duration_name = long_dur.get("emp_name")
        doc.longest_duration_number = long_dur.get("emp_number")
        doc.longest_duration_tags = ", ".join(long_dur.get("emp_tags", []))
        doc.longest_call_duration = long_dur.get("duration")

        # Highest Duration
        high_dur = result.get("highest_duration", {})
        doc.highest_duration_name = high_dur.get("emp_name")
        doc.highest_duration_number = high_dur.get("emp_number")
        doc.highest_duration_tags = ", ".join(high_dur.get("emp_tags", []))
        doc.highest_total_duration = high_dur.get("total_duration")

        doc.insert(ignore_permissions=True)
        return {"status": "success", "message": "Analysis data inserted"}

    except Exception:
        frappe.log_error(frappe.get_traceback(), _("Failed to fetch Callyzer analysis"))
        frappe.throw(_("Could not fetch analysis report"))
        
        
        
#Fetch Never Attended Report
def fetch_never_attended_calls():
    url = "https://your.callyzer.instance/call-log/never-attended"
    payload = {
        "call_from": 1691649001,
        "call_to": 1707197072,
        "emp_numbers": [],
        "emp_tags": [],
        "is_exclude_numbers": True,
        "page_no": 1,
        "page_size": 10
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_api_key_here"
    }

    response = requests.post(url, headers=headers, json=payload)
    handle_never_attended_calls(response)
    if response.status_code != 200:
        frappe.throw(f"Failed to fetch data: {response.status_code} - {response.text}")

    return response.json()

def handle_never_attended_calls(response):
    if not response.get("result"):
        frappe.msgprint("No records found.")
        return

    for emp in response["result"]:
        emp_number = emp.get("emp_number")

        # Use your existing function if employee doesn't exist
        if not frappe.db.exists("Callyzer Employee", {"employee_no": emp_number}):
            process_employee(emp)

        for log in emp.get("call_logs", []):
            if not frappe.db.exists("Callyzer Analysis", {"call_log_id": log["id"]}):
                doc = frappe.new_doc("Callyzer Analysis")
                doc.employee = emp_number
                doc.emp_code = emp.get("emp_code")
                doc.emp_name = emp.get("emp_name")
                doc.emp_number = emp_number
                doc.client_name = emp.get("client_name")
                doc.client_number = emp.get("client_number")
                doc.call_log_id = log.get("id")
                doc.duration = log.get("duration")
                doc.call_type = log.get("call_type")
                doc.call_date = log.get("call_date")
                doc.call_time = log.get("call_time")
                doc.note = log.get("note")
                doc.call_recording_url = log.get("call_recording_url")
                doc.synced_at = log.get("synced_at")
                doc.modified_at = log.get("modified_at")
                doc.insert(ignore_permissions=True)

    frappe.db.commit()



#Fetch Not Pickup By Client
def fetch_not_pickup_by_client_calls():
    url = "https://your.callyzer.instance/call-log/not-pickup-by-client"

    payload = {
        "call_from": 1691649001,
        "call_to": 1707197072,
        "call_types": ["Missed", "Rejected", "Incoming", "Outgoing"],
        "emp_numbers": [],
        "emp_tags": [],
        "is_exclude_numbers": True,
        "page_no": 1,
        "page_size": 10
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_api_key_here"
    }

    response = requests.post(url, headers=headers, json=payload)
    handle_not_pickup_by_client_calls(response)
    if response.status_code != 200:
        frappe.throw(f"Failed to fetch data: {response.status_code} - {response.text}")

    return response.json()


def handle_not_pickup_by_client_calls(response):
    if not response.get("result"):
        frappe.msgprint("No records found.")
        return

    for emp in response["result"]:
        emp_number = emp.get("emp_number")

        # Ensure employee exists via your reusable function
        if not frappe.db.exists("Callyzer Employee", {"employee_no": emp_number}):
            process_employee(emp)

        for log in emp.get("call_logs", []):
            if not frappe.db.exists("Callyzer Analysis", {"call_log_id": log["id"]}):
                doc = frappe.new_doc("Callyzer Analysis")
                doc.employee = emp_number
                doc.emp_code = emp.get("emp_code")
                doc.emp_name = emp.get("emp_name")
                doc.emp_number = emp_number
                doc.client_name = emp.get("client_name")
                doc.client_number = emp.get("client_number")
                doc.call_log_id = log.get("id")
                doc.duration = log.get("duration")
                doc.call_type = log.get("call_type")
                doc.call_date = log.get("call_date")
                doc.call_time = log.get("call_time")
                doc.note = log.get("note")
                doc.call_recording_url = log.get("call_recording_url")
                doc.synced_at = log.get("synced_at")
                doc.modified_at = log.get("modified_at")
                doc.insert(ignore_permissions=True)

    frappe.db.commit()


# Fetch Unique Clients Report

@frappe.whitelist()
def fetch_unique_clients_report():
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
    url = f"{settings.domain_api}/call-log/unique-clients"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "call_from": call_from,
        "call_to": call_to,
        "call_types": ["Incoming", "Outgoing"],
        "emp_numbers": [],
        "emp_tags": [],
        "is_exclude_numbers": True,
        "page_no": 1,
        "page_size": 10000
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        response.raise_for_status()
        return process_unique_clients_response(response.json(), company)

    except Exception:
        frappe.log_error(frappe.get_traceback(), _("Failed to fetch unique clients report"))
        frappe.throw(_("Could not fetch unique clients report"))


def process_unique_clients_response(response_json, company):
    clients = response_json.get("result", [])
    inserted = 0

    for client in clients:
        if not (client.get("client_number") and client.get("client_country_code")):
            continue

        exists = frappe.db.exists("Callyzer Unique Client", {
            "client_number": client["client_number"],
            "client_country_code": client["client_country_code"],
            "company": company
        })
        if exists:
            continue

        doc = frappe.new_doc("Callyzer Unique Client")
        doc.client_name = client.get("client_name")
        doc.client_number = client.get("client_number")
        doc.client_country_code = client.get("client_country_code")
        doc.total_calls = client.get("total_calls")
        doc.total_incoming_calls = client.get("total_incoming_calls")
        doc.total_outgoing_calls = client.get("total_outgoing_calls")
        doc.company = company

        # Optional: You can parse and store last call log info if needed
        last_call_log = client.get("last_call_log", {})
        if last_call_log:
            doc.last_call_date = last_call_log.get("call_date")
            doc.last_call_time = last_call_log.get("call_time")
            doc.last_call_type = last_call_log.get("call_type")

        doc.insert(ignore_permissions=True)
        inserted += 1

    return {"status": "success", "inserted": inserted}


# Fetch Hourly Analytics Report
@frappe.whitelist()
def fetch_hourly_analytics_report():
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

    settings = get_callyzer_settings(company)
    if not settings:
        frappe.throw(_("Callyzer settings not found for the company"))

    url = f"{settings.domain_api}/call-log/hourly-analytics"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "call_from": call_from,
        "call_to": call_to,
        "call_types": ["Missed", "Rejected", "Incoming", "Outgoing"],
        "working_hour_from": "10:00",
        "working_hour_to": "11:00",
        "is_exclude_numbers": True
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        response.raise_for_status()
        return process_hourly_analytics_response(response.json(), company, start_date)

    except Exception:
        frappe.log_error(frappe.get_traceback(), _("Failed to fetch hourly analytics report"))
        frappe.throw(_("Could not fetch hourly analytics report"))


def process_hourly_analytics_response(response_json, company, call_date):
    result = response_json.get("result", {})
    if not result:
        return {"status": "error", "message": "No result found in response"}

    total_calls = result.get("total_calls", 0)
    total_connected_calls = result.get("total_connected_calls", 0)
    total_duration = result.get("total_duration", 0)
    time_slots = result.get("time_slots", [])

    inserted = 0
    for slot in time_slots:
        doc = frappe.new_doc("Hourly Analytics")
        doc.company = company
        doc.call_date = call_date[:10]  # Extract date part
        doc.hour = slot.get("hour")
        doc.call_count = slot.get("call_count", 0)
        doc.connected_call_count = slot.get("connected_call_count", 0)
        doc.duration = slot.get("duration", 0)
        doc.total_calls = total_calls
        doc.total_connected_calls = total_connected_calls
        doc.total_duration = total_duration
        doc.insert(ignore_permissions=True)
        inserted += 1

    return {
        "status": "success",
        "inserted": inserted,
        "total_slots": len(time_slots),
        "total_calls": total_calls,
        "total_connected_calls": total_connected_calls
    }


#Fetch Day-wise Analytics Report
@frappe.whitelist()
def fetch_daywise_analytics_report():
    start_date = frappe.form_dict.get("start_date")
    end_date = frappe.form_dict.get("end_date")
    company = frappe.form_dict.get("company")

    if not (start_date and end_date and company):
        frappe.throw(_("Start Date, End Date, and Company are required"))

    try:
        call_from = format_time_timestamp_(datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S"))
        call_to = format_time_timestamp_(datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        frappe.throw(_("Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'"))

    settings = get_callyzer_settings(company)
    if not settings:
        frappe.throw(_("Callyzer settings not found for the company"))

    url = f"{settings.domain_api}/call-log/daywise-analytics"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "call_from": call_from,
        "call_to": call_to,
        "emp_numbers": [],
        "working_hour_from": "00:00",
        "working_hour_to": "20:59",
        "is_exclude_numbers": True
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
        response.raise_for_status()
        return process_daywise_analytics_response(response.json(), company)

    except Exception:
        frappe.log_error(frappe.get_traceback(), _("Failed to fetch day-wise analytics report"))
        frappe.throw(_("Could not fetch day-wise analytics report"))

def process_daywise_analytics_response(response_json, company):
    result = response_json.get("result", [])
    if not result:
        return {"status": "error", "message": "No day-wise analytics found in response"}

    inserted = 0
    for row in result:
        call_date = row.get("date")
        if not call_date:
            continue

        doc = frappe.new_doc("Daywise Analytics")
        doc.company = company
        doc.call_date = call_date
        doc.total_calls = row.get("total_calls", 0)
        doc.total_connected_calls = row.get("total_connected_calls", 0)
        doc.total_duration = row.get("total_duration", 0)
        doc.insert(ignore_permissions=True)
        inserted += 1

    return {
        "status": "success",
        "inserted": inserted,
        "days_processed": len(result)
    }

