# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrJobTransferWizard(models.TransientModel):
    _name = 'hr.job.transfer.wizard'
    _description = 'Chuyển giao chức vụ'

    source_employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên chuyển giao',
        required=True,
        readonly=True,
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        related='source_employee_id.department_id',
        readonly=True,
    )
    
    job_id = fields.Many2one(
        'hr.job',
        string='Chức vụ chuyển giao',
        related='source_employee_id.job_id',
        readonly=True,
    )
    
    target_employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên nhận chức vụ',
        required=True,
        domain="[('department_id', '=', department_id), ('id', '!=', source_employee_id), ('job_id', '!=', job_id)]",
    )
    
    note = fields.Text(string='Ghi chú')

    def action_transfer(self):
        """Transfer job from source employee to target employee."""
        self.ensure_one()
        
        if not self.source_employee_id.job_id:
            raise ValidationError("Nhân viên không có chức vụ để chuyển giao.")
        
        job = self.source_employee_id.job_id
        source_name = self.source_employee_id.name
        target_name = self.target_employee_id.name
        
        # Log history on source employee
        self.source_employee_id.message_post(
            body=f"Đã chuyển giao chức vụ [{job.name}] cho [{target_name}].",
            message_type='notification'
        )
        
        # Remove job from source (write will trigger add_User2Groups)
        self.source_employee_id.write({'job_id': False})
        
        # Check if target already has a different job to log it
        old_target_job = self.target_employee_id.job_id
        if old_target_job:
            self.target_employee_id.message_post(
                body=f"Thay đổi chức vụ từ [{old_target_job.name}] sang [{job.name}] (Nhận từ {source_name}).",
                message_type='notification'
            )
        else:
            self.target_employee_id.message_post(
                body=f"Đã nhận chức vụ [{job.name}] từ [{source_name}].",
                message_type='notification'
            )

        # Assign job to target
        self.target_employee_id.write({'job_id': job.id})
        
        return {'type': 'ir.actions.act_window_close'}

