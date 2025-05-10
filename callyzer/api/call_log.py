import frappe
import requests
import json
from callyzer.callyzer.utils import get_callyzer_settings
from callyzer.api.fetch_employee import parse_datetime
from frappe import _
from datetime import datetime

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
    """Receive data from Callyzer via webhook and process employee & call log data."""
    try:
        if frappe.request.method != "POST":
            frappe.throw(_("Webhook only accepts POST requests"), frappe.ValidationError)

        payload = frappe.request.get_json()
        if not payload:
            frappe.throw(_("Invalid or empty JSON payload"))

        if isinstance(payload, list):
            data = payload
        elif isinstance(payload, dict):
            data = payload.get("result", []) or [payload]
        else:
            frappe.throw(_("Unexpected payload format"))

        total_created = 0
        total_logs = 0

        for item in data:
            emp_number = item.get("emp_number")
            emp_name = item.get("emp_name")

            # Check if employee exists
            existing_employee = frappe.db.exists("Callyzer Employee", {"employee_no": emp_number})
            if not existing_employee:
                employee_doc = frappe.new_doc("Callyzer Employee")
                employee_doc.employee_name = emp_name
                employee_doc.employee_no = emp_number
                employee_doc.employee_code = item.get("emp_code")
                employee_doc.emp_country_code = item.get("emp_country_code")
                employee_doc.mobile_no = emp_number
                employee_doc.tags = ", ".join(item.get("emp_tags", []))
                employee_doc.insert(ignore_permissions=True)
                created_employee = employee_doc.name
                total_created += 1
            else:
                created_employee = frappe.get_value("Callyzer Employee", {"employee_number": emp_number}, "name")

            # Process call logs
            call_logs = item.get("call_logs", [])
            for call in call_logs:
                if not frappe.db.exists("Callyzer Call Log", {"external_id": call["id"]}):
                    call_log = frappe.new_doc("Callyzer Call Log")
                    call_log.employee = created_employee
                    call_log.call_log_id = call["id"]
                    call_log.client_name = call["client_name"]
                    call_log.client_country_code = call["client_country_code"]
                    call_log.client_no = call["client_number"]
                    call_log.duration = call["duration"]
                    call_log.call_type = call["call_type"]
                    call_log.call_date = call["call_date"]
                    call_log.call_time = call["call_time"]
                    call_log.note = json.dumps(call.get("note", ""))
                    call_log.call_recording_url = call["call_recording_url"]
                    call_log.crm_status = call.get("crm_status")
                    call_log.reminder_date = call.get("reminder_date")
                    call_log.reminder_time = call.get("reminder_time")
                    call_log.synced_at = parse_datetime(call.get("synced_at"))
                    call_log.modified_at = parse_datetime(call.get("modified_at"))

                    call_log.insert(ignore_permissions=True)
                    total_logs += 1

        return {
            "status": "success",
            "employees_created": total_created,
            "call_logs_created": total_logs
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Webhook: Failed to process Callyzer data")
        return {"status": "error", "message": "Processing failed"}
