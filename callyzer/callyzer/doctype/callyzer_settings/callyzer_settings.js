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

        frm.add_custom_button(__('Fetch Summary Report'), function() {
            const today = frappe.datetime.get_today();
            const one_month_ago = frappe.datetime.add_months(today, -1);

            const d = new frappe.ui.Dialog({
                title: 'Fetch Summary Report',
                fields: [
                    {
                        label: 'Start Date',
                        fieldname: 'start_date',
                        fieldtype: 'Date',
                        default: one_month_ago,
                        reqd: true
                    },
                    {
                        label: 'End Date',
                        fieldname: 'end_date',
                        fieldtype: 'Date',
                        default: today,
                        reqd: true
                    }
                ],
                primary_action_label: 'Fetch',
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        method: 'callyzer.api.call_log.fetch_summary_report',
                        args: {
                            start_date: values.start_date,
                            end_date: values.end_date,
                            company: frm.doc.company
                        },
                        callback: function(r) {
                            if (r.message) {
                                const summary = r.message;
                                let content = `<div><strong>Summary Report</strong></div><br/>`;
                                for (const [key, value] of Object.entries(summary)) {
                                    content += `<div><b>${frappe.utils.to_title_case(key.replace(/_/g, ' '))}:</b> ${value}</div>`;
                                }

                                const result_dialog = new frappe.ui.Dialog({
                                    title: 'Summary Report Result',
                                    size: 'large',
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
