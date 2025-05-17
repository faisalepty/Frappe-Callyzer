frappe.ui.form.on('Callyzer Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Fetch Employees'), function() {
            frappe.call({
                method: "callyzer.api.fetch_employee.fetch_employees",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        }, __('Action'));

        frm.add_custom_button(__('Fetch Call By ID'), function() {
            let d = new frappe.ui.Dialog({
                title: 'Enter Call Log Unique ID',
                fields: [
                    {
                        label: 'Unique ID',
                        fieldname: 'unique_id',
                        fieldtype: 'Data',
                        reqd: true
                    }
                ],
                primary_action_label: 'Send',
                primary_action(values) {
                    d.hide();

                    frappe.call({
                        method: "callyzer.api.fetch_call_history.fetch_call_history_by_ids",
                        args: {
                            unique_ids: [values.unique_id],
                            company: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === "success") {
                                frappe.msgprint(__("Fetched and inserted {0} call log(s)", [r.message.inserted]));
                            } else {
                                frappe.msgprint(__("Call fetch failed"));
                            }
                        }
                    });
                }
            });

            d.show();
        }, __('Action'));

        // Remove Call Recording Button
        frm.add_custom_button(__('Remove Call Recording'), function() {
            let d = new frappe.ui.Dialog({
                title: 'Enter Call Log Unique ID(s)',
                fields: [
                    {
                        label: 'Unique ID(s) (comma separated)',
                        fieldname: 'unique_ids',
                        fieldtype: 'Small Text',
                        reqd: true
                    }
                ],
                primary_action_label: 'Remove',
                primary_action(values) {
                    d.hide();
                    let ids = values.unique_ids.split(',').map(id => id.trim()).filter(Boolean);

                    frappe.call({
                        method: "callyzer.api.call_recording.remove_call_recording",
                        args: {
                            unique_ids: ids,
                            company: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message.status === "success") {
                                frappe.msgprint(__("Call recording(s) removed successfully."));
                            } else {
                                frappe.msgprint(__("Failed to remove recording: ") + r.message.message);
                            }
                        }
                    });
                }
            });
            d.show();
        }, __('Action'));
    

        frm.add_custom_button(__('Fetch Summary Report'), function() {
            const today = frappe.datetime.get_datetime_as_string(); 
            const one_month_ago = frappe.datetime.add_days(today, -1);

            const d = new frappe.ui.Dialog({
                title: 'Fetch Summary Report',
                fields: [
                    {
                        label: 'Start Date',
                        fieldname: 'start_date',
                        fieldtype: 'Datetime',
                        default: one_month_ago,
                        reqd: true
                    },
                    {
                        label: 'End Date',
                        fieldname: 'end_date',
                        fieldtype: 'Datetime',
                        default: today,
                        reqd: true
                    },
                ],
                primary_action_label: 'Fetch',
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        // method: 'callyzer.api.call_log.fetch_summary_report',
                        method: 'callyzer.api.call_log.fetch_call_history_report',

                        args: {
                            start_date: values.start_date,
                            end_date: values.end_date,
                            company: frm.doc.company
                        },
                        callback: function(r) {
                            if (r.message) {
                                const summary = r.message.result;
                                let content = `<div><strong>Summary Report</strong></div><br/>`;
                                for (const [key, value] of Object.entries(summary)) {
                                    content += `<div><b>${frappe.utils.to_title_case(key.replace(/_/g, ' '))}:</b> ${value}</div>`;
                                }

                                const result_dialog = new frappe.ui.Dialog({
                                    title: 'Summary Report Result',
                                    size: 'large',
                                    fields: [
                                                {
                                                    fieldtype: 'HTML',
                                                    fieldname: 'summary_html',
                                                    options: content
                                                }
                                            ],
                                    primary_action_label: 'Print',
                                    primary_action() {
                                        const print_window = window.open('', '', 'width=800,height=600');
                                        print_window.document.write(`<html><head><title>Summary Report</title></head><body>${content}</body></html>`);
                                        print_window.document.close();
                                        print_window.print();
                                    }
                                });

    result_dialog.set_message(content);
    result_dialog.show();
}

                        }
                    });
                }
            });
            d.show();
        }, __('Action'));
    }
});
