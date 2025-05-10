

import frappe
from datetime import datetime
from frappe import _
import json

def get_callyzer_settings(company):
    settings = frappe.get_all("Callyzer Settings", filters={"is_active": 1, "company":company}, fields=["name", "domain_api", "api_key", "company", "call_log"])
    return settings[0] if settings else None


