# -*- coding: utf-8 -*-
import odoo
from odoo import models, api, fields, _, tools
from odoo.exceptions import ValidationError

from imaplib import IMAP4
import logging

_logger = logging.getLogger(__name__)

MAX_IMAP_MESSAGES = 10
MAX_POP_MESSAGES = 10


import threading
import select

# Global dict to store running idle threads: {server_id: thread_object}
_IDLE_THREADS = {}
_IDLE_STOP_EVENTS = {}


class FetchmailServer(models.Model):
    _inherit = 'fetchmail.server'

    is_imap_idle_running = fields.Boolean(
        string='Đang Lắng Nghe Real-time',
        compute='_compute_is_imap_idle_running',
        help='Trạng thái của tiến trình theo dõi hộp thư đến.',
    )

    def _compute_is_imap_idle_running(self):
        for server in self:
            server.is_imap_idle_running = server.id in _IDLE_THREADS and _IDLE_THREADS[server.id].is_alive()

    def action_mark_all_as_read(self):
        """Đánh dấu tất cả mail chưa đọc là đã đọc trên server (IMAP)."""
        self.ensure_one()
        if self.server_type != 'imap':
            raise ValidationError(_('Tính năng này chỉ hỗ trợ giao thức IMAP.'))

        try:
            imap_server = self.connect()
            imap_server.select()
            # Search UNSEEN
            result, data = imap_server.search(None, '(UNSEEN)')
            unseen_nums = data[0].split()
            if unseen_nums:
                _logger.info('Bắt đầu đánh dấu đã đọc %s email trên server %s', len(unseen_nums), self.name)
                # chunking để tránh command quá dài
                for i in range(0, len(unseen_nums), 500):
                    chunk = unseen_nums[i:i+500]
                    ids_str = (b',').join(chunk).decode()
                    imap_server.store(ids_str, '+FLAGS', '\\Seen')
                _logger.info('Đã đánh dấu xong cho server %s', self.name)

            imap_server.close()
            imap_server.logout()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Thành công'),
                    'message': _('Đã đánh dấu toàn bộ email là đã đọc trên máy chủ.'),
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error('Lỗi khi đánh dấu đã đọc: %s', e, exc_info=True)
            raise ValidationError(_('Không thể thực hiện: %s', e))

    def action_start_imap_idle(self):
        """Bắt đầu thread lắng nghe IMAP IDLE."""
        self.ensure_one()
        if self.server_type != 'imap':
            raise ValidationError(_('Chỉ hỗ trợ IMAP.'))

        if self.id in _IDLE_THREADS and _IDLE_THREADS[self.id].is_alive():
            return True

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._imap_idle_worker,
            args=(self.id, self.env.registry.db_name, stop_event),
            name=f'IMAP_IDLE_{self.id}',
            daemon=True,
        )
        _IDLE_THREADS[self.id] = thread
        _IDLE_STOP_EVENTS[self.id] = stop_event
        thread.start()
        _logger.info('Đã bắt đầu IMAP IDLE listener cho server ID: %s', self.id)
        return True

    def action_stop_imap_idle(self):
        """Dừng thread lắng nghe."""
        self.ensure_one()
        if self.id in _IDLE_STOP_EVENTS:
            _IDLE_STOP_EVENTS[self.id].set()
            _logger.info('Đã gửi yêu cầu dừng IMAP IDLE cho server ID: %s', self.id)
        return True

    def _imap_idle_worker(self, server_id, db_name, stop_event):
        """Worker chạy trong background thread."""
        _logger.info('Thread IMAP IDLE bắt đầu chạy (DB: %s, Server: %s)', db_name, server_id)

        while not stop_event.is_set():
            imap_server = None
            try:
                # Tạo environment mới cho thread
                db_registry = odoo.modules.registry.Registry(db_name)
                with db_registry.cursor() as cr:
                    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
                    server = env['fetchmail.server'].browse(server_id)
                    if not server.exists() or server.state != 'done':
                        _logger.warning('Server %s không khả dụng hoặc chưa xác nhận. Dừng thread.', server_id)
                        break

                    # IDLE connection - CHỈ dùng để lắng nghe, KHÔNG fetch qua connection này
                    imap_server = server.connect()
                    imap_server.select()
                    raw_imap = imap_server.__obj__

                    _logger.info('IMAP IDLE: Kết nối thành công, bắt đầu lắng nghe trên server %s', server.name)

                    # Vòng lặp IDLE
                    idle_tag_counter = 0
                    while not stop_event.is_set():
                        # Gửi lệnh IDLE với tag đơn giản
                        idle_tag_counter += 1
                        tag = f'IDLE{idle_tag_counter}'.encode()
                        raw_imap.send(tag + b' IDLE\r\n')

                        # Đọc continuation response
                        cont_resp = raw_imap.readline()
                        _logger.info('IMAP IDLE response: %s', cont_resp)

                        if not cont_resp or b'+' not in cont_resp:
                            _logger.warning(
                                'IMAP IDLE: Server không hỗ trợ IDLE hoặc lỗi kết nối. Response: %s', cont_resp,
                            )
                            break

                        # Đã vào chế độ IDLE - chờ thông báo từ server
                        sock = raw_imap.socket()
                        has_new_mail = False
                        while not stop_event.is_set():
                            readable, _, _ = select.select([sock], [], [], 30.0)
                            if readable:
                                line = raw_imap.readline()
                                _logger.info('IMAP IDLE data: %s', line)
                                if b'EXISTS' in line or b'RECENT' in line:
                                    _logger.info('IMAP IDLE: Phát hiện email mới trên %s!', server.name)
                                    has_new_mail = True
                                    break
                            else:
                                # Timeout 30s, thoát IDLE để re-IDLE (giữ connection alive)
                                break

                        # Kết thúc IDLE
                        raw_imap.send(b'DONE\r\n')
                        # Đọc tagged response
                        done_resp = raw_imap.readline()
                        _logger.debug('IMAP IDLE DONE response: %s', done_resp)

                        if has_new_mail:
                            # Fetch mail qua connection RIÊNG (fetch_mail tự connect/close)
                            server.fetch_mail(raise_exception=False)
                            cr.commit()

            except Exception as e:
                _logger.error('Lỗi trong IMAP IDLE worker (Server %s): %s', server_id, e, exc_info=True)
                # Đợi một chút trước khi kết nối lại
                stop_event.wait(30.0)
            finally:
                if imap_server:
                    try:
                        imap_server.logout()
                    except Exception:
                        pass

        _logger.info('Thread IMAP IDLE đã kết thúc (Server: %s)', server_id)
        if server_id in _IDLE_THREADS:
            del _IDLE_THREADS[server_id]
        if server_id in _IDLE_STOP_EVENTS:
            del _IDLE_STOP_EVENTS[server_id]

    def button_confirm_login(self):
        """Override để hiển thị thông báo kết quả kiểm tra kết nối."""
        super().button_confirm_login()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Kết nối thành công'),
                'message': _('Đã kết nối thành công tới máy chủ mail đến.'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }

    def _process_mail_safely(self, mail_thread, server, raw_mail, additionnal_context):
        """
        Xử lý 1 email an toàn.
        - Parse email trước bằng Python email module
        - Nếu 'No possible route found' → tạo mail.message để giám sát
        - Lỗi khác → log bình thường

        Returns:
            (res_id, skipped, failed)
        """
        # 1. Parse email header trước (luôn thành công, không phụ thuộc Odoo)
        import email as email_lib
        import email.policy
        import email.utils
        try:
            if isinstance(raw_mail, bytes):
                parsed_msg = email_lib.message_from_bytes(raw_mail, policy=email.policy.default)
            else:
                parsed_msg = email_lib.message_from_string(raw_mail, policy=email.policy.default)
            email_subject = parsed_msg.get('Subject', '(Không có tiêu đề)')
            email_from = parsed_msg.get('From', '')
            email_to = parsed_msg.get('To', '')
            email_message_id = parsed_msg.get('Message-Id', '')
            email_reply_to = parsed_msg.get('Reply-To', '')
            email_date_str = parsed_msg.get('Date', '')
            # Parse body (lấy text/html hoặc text/plain)
            email_body = ''
            if parsed_msg.is_multipart():
                for part in parsed_msg.walk():
                    ctype = part.get_content_type()
                    if ctype == 'text/html':
                        email_body = part.get_content()
                        break
                    elif ctype == 'text/plain' and not email_body:
                        email_body = '<pre>' + str(part.get_content()) + '</pre>'
            else:
                ctype = parsed_msg.get_content_type()
                if ctype == 'text/html':
                    email_body = parsed_msg.get_content()
                elif ctype == 'text/plain':
                    email_body = '<pre>' + str(parsed_msg.get_content()) + '</pre>'
        except Exception:
            email_subject = '(Lỗi parse email)'
            email_from = ''
            email_body = ''
            email_message_id = ''
            email_reply_to = ''

        # 2. Thử message_process (xử lý routing bình thường)
        try:
            res_id = mail_thread.with_context(**additionnal_context).message_process(
                server.object_id.model,
                raw_mail,
                save_original=server.original,
                strip_attachments=(not server.attach),
            )
            return res_id, False, False
        except ValueError as e:
            if 'No possible route found' in str(e):
                # 3. Không có route → tạo mail.message để giám sát
                try:
                    new_msg = self.env['mail.message'].sudo().create({
                        'message_type': 'email',
                        'subject': email_subject or '(Không có tiêu đề)',
                        'email_from': email_from,
                        'body': email_body,
                        'date': fields.Datetime.now(),
                        'message_id': email_message_id,
                        'reply_to': email_reply_to,
                    })
                    _logger.info(
                        'Lưu email không có route (server: %s, from: %s, subject: %s, id: %s)',
                        server.name, email_from, email_subject, new_msg.id,
                    )
                except Exception as create_err:
                    _logger.warning(
                        'LỖI tạo mail.message cho email không có route (server: %s, from: %s): %s',
                        server.name, email_from, str(create_err), exc_info=True,
                    )
                return None, True, False  # skipped, not failed
            _logger.info(
                'Lỗi xử lý mail từ %s server %s: %s',
                server.server_type, server.name, str(e), exc_info=True,
            )
            return None, False, True
        except Exception as e:
            _logger.info(
                'Lỗi xử lý mail từ %s server %s: %s',
                server.server_type, server.name, str(e), exc_info=True,
            )
            return None, False, True

    def fetch_mail(self, raise_exception=True):
        """
        Override fetch_mail gốc để:
        - Bắt 'No possible route found' → skip im lặng thay vì log traceback
        - Giảm tải log khi inbox có nhiều email thông báo (YouTube, Facebook, etc.)
        """
        additionnal_context = {
            'fetchmail_cron_running': True
        }
        MailThread = self.env['mail.thread']

        for server in self:
            _logger.info(
                'start checking for new emails on %s server %s',
                server.server_type, server.name,
            )
            additionnal_context['default_fetchmail_server_id'] = server.id
            count, failed, skipped = 0, 0, 0
            imap_server = None
            pop_server = None
            connection_type = server._get_connection_type()

            if connection_type == 'imap':
                try:
                    imap_server = server.connect()
                    imap_server.select()
                    result, data = imap_server.search(None, '(UNSEEN)')
                    unseen_nums = data[0].split()
                    # Giới hạn số email xử lý mỗi lần cron chạy để tránh timeout
                    for num in unseen_nums[:MAX_IMAP_MESSAGES]:
                        result, data = imap_server.fetch(num, '(RFC822)')
                        imap_server.store(num, '-FLAGS', '\\Seen')

                        res_id, is_skipped, is_failed = self._process_mail_safely(
                            MailThread, server, data[0][1], additionnal_context,
                        )
                        if is_failed:
                            failed += 1
                        if is_skipped:
                            skipped += 1

                        imap_server.store(num, '+FLAGS', '\\Seen')
                        self._cr.commit()
                        count += 1

                    _logger.info(
                        'Fetched %d email(s) on %s server %s; %d succeeded, %d skipped (no route), %d failed.',
                        count, server.server_type, server.name,
                        (count - failed - skipped), skipped, failed,
                    )
                except Exception as e:
                    if raise_exception:
                        raise ValidationError(
                            _("Couldn't get your emails. Check out the error message below for more info:\n%s", e)
                        ) from e
                    else:
                        _logger.info(
                            'General failure when trying to fetch mail from %s server %s.',
                            server.server_type, server.name, exc_info=True,
                        )
                finally:
                    if imap_server:
                        try:
                            imap_server.close()
                            imap_server.logout()
                        except (OSError, IMAP4.abort):
                            _logger.warning(
                                'Failed to properly finish imap connection: %s.',
                                server.name, exc_info=True,
                            )

            elif connection_type == 'pop':
                try:
                    while True:
                        failed_in_loop = 0
                        num = 0
                        pop_server = server.connect()
                        (num_messages, total_size) = pop_server.stat()
                        pop_server.list()
                        for num in range(1, min(MAX_POP_MESSAGES, num_messages) + 1):
                            (header, messages, octets) = pop_server.retr(num)
                            message = (b'\n').join(messages)

                            res_id, is_skipped, is_failed = self._process_mail_safely(
                                MailThread, server, message, additionnal_context,
                            )
                            if not is_failed and not is_skipped:
                                pop_server.dele(num)
                            if is_failed:
                                failed += 1
                                failed_in_loop += 1
                            if is_skipped:
                                skipped += 1

                            self.env.cr.commit()

                        _logger.info(
                            'Fetched %d email(s) on %s server %s; %d succeeded, %d skipped (no route), %d failed.',
                            num, server.server_type, server.name,
                            (num - failed_in_loop - skipped), skipped, failed_in_loop,
                        )
                        if num_messages < MAX_POP_MESSAGES or failed_in_loop == num:
                            break
                        pop_server.quit()
                except Exception as e:
                    if raise_exception:
                        raise ValidationError(
                            _("Couldn't get your emails. Check out the error message below for more info:\n%s", e)
                        ) from e
                    else:
                        _logger.info(
                            'General failure when trying to fetch mail from %s server %s.',
                            server.server_type, server.name, exc_info=True,
                        )
                finally:
                    if pop_server:
                        try:
                            pop_server.quit()
                        except OSError:
                            _logger.warning(
                                'Failed to properly finish pop connection: %s.',
                                server.name, exc_info=True,
                            )

            server.write({'date': fields.Datetime.now()})
        return True
