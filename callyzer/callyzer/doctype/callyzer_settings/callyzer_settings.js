// Copyright (c) 2025, Mania and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Callyzer Settings", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Callyzer Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Fetch Employees'), function() {
            frappe.call({
                method: "your_app_path.callyzer_settings.fetch_employees",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        });
    }
});
