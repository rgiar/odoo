# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.addons.resource.models.resource import Intervals

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    benefit_type_id = fields.Many2one('hr.benefit.type', string='Benefit Type')


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.multi
    def _get_benefits_values(self):
        vals_list = []
        for leave in self:
            benefit_type = leave.holiday_status_id.benefit_type_id
            vals_list += [{
                'name': "%s%s" % (benefit_type.name + ": " if benefit_type else "", leave.employee_id.name),
                'date_start': leave.date_from,
                'date_stop': leave.date_to,
                'benefit_type_id': benefit_type.id,
                'display_warning': not bool(benefit_type),
                'employee_id': leave.employee_id.id,
                'leave_id': leave.id,
                'state': 'confirmed',
            }]
        return vals_list

    @api.multi
    def _cancel_benefit_conflict(self):
        benefits = self.env['hr.benefit'].search([('leave_id', 'in', self.ids)])
        if benefits:
            vals_list = self._get_benefits_values()

            # create new benefits where the leave does not cover the full benefit
            benefits_intervals = Intervals(intervals=[(b.date_start, b.date_stop, b) for b in benefits])
            leave_intervals = Intervals(intervals=[(l.date_from, l.date_to, l) for l in self])
            remaining_benefits = benefits_intervals - leave_intervals

            for interval in remaining_benefits:
                benefit = interval[2]
                leave = benefit.leave_id
                benefit_type = benefit.benefit_type_id
                employee = benefit.employee_id

                benefit_start = interval[0] + relativedelta(seconds=1) if leave.date_to == interval[0] else interval[0]
                benefit_stop = interval[1] - relativedelta(seconds=1) if leave.date_from == interval[1] else interval[1]

                vals_list += [{
                    'name': "%s: %s" % (benefit_type.name, employee.name),
                    'date_start': benefit_start,
                    'date_stop': benefit_stop,
                    'benefit_type_id': benefit_type.id,
                    'employee_id': employee.id,
                    'state': 'confirmed',
                }]

            date_start = min(benefits.mapped('date_start'))
            date_stop = max(benefits.mapped('date_stop'))
            self.env['hr.benefit']._safe_duplicate_create(vals_list, date_start, date_stop)
            benefits.unlink()

    @api.multi
    def action_validate(self):
        super(HrLeave, self).action_validate()
        self.sudo()._cancel_benefit_conflict()
        calendar_leaves = self.env['resource.calendar.leaves'].search([('holiday_id', 'in', self.ids)])
        calendar_leaves.write({'benefit_type_id': self.holiday_status_id.benefit_type_id.id})
        return True

    @api.multi
    def action_refuse(self):
        super(HrLeave, self).action_refuse()
        benefits = self.env['hr.benefit'].sudo().search([('leave_id', 'in', self.ids)])
        benefits.write({'display_warning': False, 'leave_id': None})
        return True
