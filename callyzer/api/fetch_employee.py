

import frappe
from datetime import datetime
import json

@frappe.whitelist()
def fetch_employees():
    settings_list = get_callyzer_settings()
    total_created = 0

    for setting in settings_list:
        try:
            res = fetch_employee_data_from_api(setting)
            data = res.get("result", [])
            created = process_employee_response(data)
            total_created += created
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to fetch employees for {setting.name}")

    frappe.msgprint(f"Successfully created {total_created} new employee(s).")


def process_employee_response(data):
    created = 0
    for item in data:
        if frappe.db.exists("Callyzer Employee", {"employee_no": item.get("emp_number")}):
            continue
        process_employee(item)
        created += 1

    return created


def fetch_employee_data_from_api(setting):
    url = setting.domain_api + setting.employee
    headers = {
        "spi-key": setting.api_key,
        "company": setting.company
    }
    return frappe.make_get_request(url, headers=headers)

def get_callyzer_settings():
    return frappe.get_all(
        "Callyzer Settings",
        fields=["name", "domain_api", "employee", "call_log", "api_key", "company"]
    )


@frappe.whitelist(allow_guest=True)
def callyzer_employee_webhook():
    """Receive data from Callyzer via webhook and process it."""
    try:
        if frappe.request.method != "POST":
            frappe.throw(_("Webhook only accepts POST requests"), frappe.ValidationError)

        payload = frappe.request.get_json()
        if not payload:
            frappe.throw(_("Invalid or empty JSON payload"))

        data = payload.get("result", []) or [payload]
        created = process_employee_response(data)

        return {"status": "success", "created": created}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Webhook: Failed to process Callyzer Employee data")
        return {"status": "error", "message": "Processing failed"}
    

def parse_datetime(value):
    if not value:
        return None
    try:
        clean_value = value.split(' ')[0] + ' ' + value.split(' ')[1]
        return datetime.strptime(clean_value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def process_employee(item):
    """Create employee if not exists and return employee name and creation status."""
    emp_number = item.get("emp_number")

    existing = frappe.db.exists("Callyzer Employee", {"employee_no": emp_number})
    if existing:
        return frappe.get_value("Callyzer Employee", {"employee_no": emp_number}, "name"), False

    doc = frappe.new_doc("Callyzer Employee")
    doc.employee_name = item.get("emp_name")
    doc.employee_code = item.get("emp_code")
    doc.emp_country_code = item.get("emp_country_code")
    doc.employee_no = item.get("emp_number")
    doc.tags = ", ".join(item.get("emp_tags", []))
    doc.app_version = item.get("app_version")
    doc.registered_at = parse_datetime(item.get("registered_at"))
    doc.modified_at = parse_datetime(item.get("modified_at"))
    doc.last_call_at = parse_datetime(item.get("last_call_at"))
    doc.last_sync_req_at = parse_datetime(item.get("last_sync_req_at"))
    doc.is_lead_active = item.get("is_lead_active")
    doc.is_call_recording_active = item.get("is_call_recording_active")
    doc.device_details = json.dumps(item.get("device_details", {}))
    doc.device_preference = json.dumps(item.get("device_preference", {}))
    doc.app_settings = json.dumps(item.get("app_settings", {}))
    
    doc.insert(ignore_permissions=True)
    return doc.name, True
