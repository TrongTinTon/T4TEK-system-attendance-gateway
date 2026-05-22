# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class MailRenderMixin(models.AbstractModel):
    _inherit = 'mail.render.mixin'

    def _check_access_right_dynamic_template(self):
        if (
            not self.env.su
            and not self.env.user.has_group('mail.group_mail_template_editor')
            and not self.env.user.has_group('t4_admin_center.group_admin_center')
            and self._has_unsafe_expression()
        ):
            group = self.env.ref('mail.group_mail_template_editor')
            raise AccessError(
                _('Only members of %(group_name)s group are allowed to edit templates containing sensible placeholders',
                  group_name=group.name)
            )


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    smtp_user = fields.Char(
        string='Username',
        help='Tên đăng nhập tùy chọn để xác thực máy chủ gửi thư',
        groups='base.group_system,t4_admin_center.group_admin_center',
    )
    smtp_pass = fields.Char(
        string='Password',
        help='Mật khẩu tùy chọn để xác thực máy chủ gửi thư',
        groups='base.group_system,t4_admin_center.group_admin_center',
    )


class MailMessage(models.Model):
    _inherit = 'mail.message'

    def unlink(self):
        res = super(MailMessage, self).unlink()
        return res


class MailTemplatePreview(models.TransientModel):
    _inherit = 'mail.template.preview'

    @api.depends('mail_template_id')
    def _compute_resource_ref(self):
        for preview in self:
            mail_template = preview.mail_template_id.sudo()
            model = mail_template.model_id.model if mail_template.model_id else False
            if not model:
                preview.resource_ref = False
                continue
            res = self.env[model].search([], limit=1)
            preview.resource_ref = f'{model},{res.id}' if res else False


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    active = fields.Boolean()

    def action_preview_template(self):
        """Mở wizard xem trước mẫu email."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Xem Trước Mẫu Email'),
            'res_model': 'mail.template.preview',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_mail_template_id': self.id},
        }


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def _send(self, auto_commit=False, raise_exception=False, smtp_session=None, alias_domain_id=False,
              mail_server=False, post_send_callback=None):
        """
        Ghi đè phương thức gửi mail để kiểm tra cấu hình 'Tắt mail giao dịch'.
        """
        # Danh sách các model LUÔN được phép gửi mail (Whitelist)
        SAFE_MODELS = [
            'res.users',
            'auth.signup.token',
        ]

        mails_to_send = self.env['mail.mail']
        for mail in self:
            # 1. Nếu email thuộc model an toàn hoặc không có model -> Cho phép gửi
            if not mail.model or mail.model in SAFE_MODELS:
                mails_to_send |= mail
                _logger.info(
                    '=======================Cho phép gửi mail (ID: %s, Model: %s)=======================',
                    mail.id, mail.model,
                )
                continue

            # 2. Kiểm tra xem có người nhận nào yêu cầu chặn không
            should_block = False
            for partner in mail.partner_ids:
                # Kiểm tra trực tiếp Partner hoặc Công ty của họ
                if partner.x_disable_transactional_mail or (
                    partner.company_id and partner.company_id.partner_id.x_disable_transactional_mail
                ):
                    should_block = True
                    break

            if should_block:
                _logger.info(
                    '*************Chặn gửi mail giao dịch (ID: %s, Model: %s) do cấu hình x_disable_transactional_mail*************',
                    mail.id, mail.model,
                )
                mail.state = 'cancel'
            else:
                mails_to_send |= mail

        if not mails_to_send:
            return True

        return super(MailMail, mails_to_send)._send(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            smtp_session=smtp_session,
            alias_domain_id=alias_domain_id,
            mail_server=mail_server,
            post_send_callback=post_send_callback,
        )
