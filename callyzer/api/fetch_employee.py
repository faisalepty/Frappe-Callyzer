

import frappe

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
        if frappe.db.exists("Callyzer Employee", {"emp_number": item.get("emp_number")}):
            continue

        doc = frappe.new_doc("Callyzer Employee")
        doc.emp_name = item.get("emp_name")
        doc.emp_code = item.get("emp_code")
        doc.emp_country_code = item.get("emp_country_code")
        doc.emp_number = item.get("emp_number")
        doc.emp_tags = ", ".join(item.get("emp_tags", []))
        doc.app_version = item.get("app_version")
        doc.registered_at = item.get("registered_at")
        doc.modified_at = item.get("modified_at")
        doc.last_call_at = item.get("last_call_at")
        doc.last_sync_req_at = item.get("last_sync_req_at")
        doc.is_lead_active = item.get("is_lead_active")
        doc.is_call_recording_active = item.get("is_call_recording_active")
     
        doc.insert(ignore_permissions=True)
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

