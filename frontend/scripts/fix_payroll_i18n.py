#!/usr/bin/env python3
"""Add missing i18n keys for payroll modules and generate replacements."""

import json, re, os

I18N_DIR = '/Users/wangchen/Desktop/TACAI/tacone/frontend/src/i18n'
SRC_DIR = '/Users/wangchen/Desktop/TACAI/tacone/frontend/src/modules/payroll'

# ── New i18n keys to add (zh, en, ja) ──────────────────────────
NEW_KEYS = {
    # ── Pre-existing missing (31 keys) ──
    "payroll.jp.calculation_summary": {
        "zh": "计算汇总", "en": "Calculation Summary", "ja": "計算サマリー"
    },
    "field.days": {
        "zh": "天数", "en": "Days", "ja": "日数"
    },
    "action.created": {
        "zh": "已创建", "en": "Created", "ja": "作成済み"
    },
    "action.confirm_deactivate_entity": {
        "zh": "确认停用此法人实体？", "en": "Confirm deactivate this entity?", "ja": "この法人を無効化しますか？"
    },
    # Invoice field keys (pre-existing gaps)
    "field.amount": {"zh": "金额", "en": "Amount", "ja": "金額"},
    "field.balance": {"zh": "余额", "en": "Balance", "ja": "残高"},
    "field.customer_name": {"zh": "客户名称", "en": "Customer Name", "ja": "顧客名"},
    "field.default_currency": {"zh": "默认币种", "en": "Default Currency", "ja": "既定通貨"},
    "field.default_tax_rate": {"zh": "默认税率", "en": "Default Tax Rate", "ja": "既定税率"},
    "field.description": {"zh": "描述", "en": "Description", "ja": "説明"},
    "field.due_date": {"zh": "到期日", "en": "Due Date", "ja": "期限日"},
    "field.estimated_amount": {"zh": "预估金额", "en": "Estimated Amount", "ja": "見積金額"},
    "field.invoice_date": {"zh": "发票日期", "en": "Invoice Date", "ja": "請求日"},
    "field.invoice_number": {"zh": "发票编号", "en": "Invoice Number", "ja": "請求書番号"},
    "field.main_recipient_email": {"zh": "主收件人邮箱", "en": "Main Recipient Email", "ja": "主受信者メール"},
    "field.main_recipient_name": {"zh": "主收件人姓名", "en": "Main Recipient Name", "ja": "主受信者名"},
    "field.overdue_days": {"zh": "逾期天数", "en": "Overdue Days", "ja": "延滞日数"},
    "field.payment_date": {"zh": "付款日期", "en": "Payment Date", "ja": "支払日"},
    "field.payment_method": {"zh": "付款方式", "en": "Payment Method", "ja": "支払方法"},
    "field.payment_terms_days": {"zh": "付款条件天数", "en": "Payment Terms Days", "ja": "支払条件日数"},
    "field.period_end": {"zh": "期间结束", "en": "Period End", "ja": "期間終了"},
    "field.period_start": {"zh": "期间开始", "en": "Period Start", "ja": "期間開始"},
    "field.project_id": {"zh": "项目", "en": "Project", "ja": "案件"},
    "field.quantity": {"zh": "数量", "en": "Quantity", "ja": "数量"},
    "field.reference_number": {"zh": "参考编号", "en": "Reference Number", "ja": "参照番号"},
    "field.subtotal": {"zh": "小计", "en": "Subtotal", "ja": "小計"},
    "field.tax_amount": {"zh": "税额", "en": "Tax Amount", "ja": "税額"},
    "field.tax_rate": {"zh": "税率", "en": "Tax Rate", "ja": "税率"},
    "field.total_amount": {"zh": "总金额", "en": "Total Amount", "ja": "合計金額"},
    "field.unit_price": {"zh": "单价", "en": "Unit Price", "ja": "単価"},

    # ── Payroll JP shared ──
    "payroll.jp.sync_from_employee_admin": {"zh": "从员工管理同步", "en": "Sync from Employee Admin", "ja": "Employee Adminから同期"},
    "payroll.jp.edit_record_title": {"zh": "编辑记录 — {name}", "en": "Edit Record — {name}", "ja": "レコード編集 — {name}"},

    # ── Payroll CN ──
    "payroll.cn.employee_deactivated": {"zh": "员工已停用", "en": "Employee deactivated", "ja": "社員を無効化しました"},
    "payroll.cn.employee_activated": {"zh": "员工已激活", "en": "Employee activated", "ja": "社員を有効化しました"},
    "payroll.cn.employee_created": {"zh": "员工已创建", "en": "Employee created", "ja": "社員を作成しました"},
    "payroll.cn.employee_updated": {"zh": "员工已更新", "en": "Employee updated", "ja": "社員を更新しました"},
    "payroll.cn.new_employee_config": {"zh": "新增员工工资配置", "en": "New Employee Payroll Config", "ja": "新規社員給与設定"},
    "payroll.cn.edit_employee_config": {"zh": "编辑员工工资配置", "en": "Edit Employee Payroll Config", "ja": "社員給与設定編集"},
    "payroll.cn.import_from_employees": {"zh": "从员工管理导入", "en": "Import from Employee Admin", "ja": "Employee Adminからインポート"},
    "payroll.cn.section_basic_info": {"zh": "📋 基本信息", "en": "📋 Basic Info", "ja": "📋 基本情報"},
    "payroll.cn.section_salary_structure": {"zh": "💰 工资结构", "en": "💰 Salary Structure", "ja": "💰 給与構成"},
    "payroll.cn.section_social_insurance": {"zh": "🏦 社保与公积金", "en": "🏦 Social Insurance & Housing Fund", "ja": "🏦 社会保険・住宅積立金"},
    "payroll.cn.section_bank": {"zh": "🏧 银行信息", "en": "🏧 Bank Info", "ja": "🏧 銀行情報"},
    "payroll.cn.section_notes": {"zh": "📝 备注", "en": "📝 Notes", "ja": "📝 備考"},
    "payroll.cn.salary_type_monthly": {"zh": "月薪制", "en": "Monthly Salary", "ja": "月給制"},
    "payroll.cn.salary_type_daily": {"zh": "日薪制", "en": "Daily Wage", "ja": "日給制"},
    "payroll.cn.salary_type_hourly": {"zh": "时薪制", "en": "Hourly Wage", "ja": "時給制"},
    "payroll.cn.monthly_salary": {"zh": "月薪", "en": "Monthly Salary", "ja": "月給"},
    "payroll.cn.daily_salary": {"zh": "日薪", "en": "Daily Wage", "ja": "日給"},
    "payroll.cn.hourly_salary": {"zh": "时薪", "en": "Hourly Wage", "ja": "時給"},
    "payroll.cn.checking_account": {"zh": "支票账户", "en": "Checking", "ja": "当座"},
    "payroll.cn.savings_account": {"zh": "储蓄账户", "en": "Savings", "ja": "普通"},
    "payroll.cn.insurance_city": {"zh": "参保城市", "en": "Insurance City", "ja": "保険加入都市"},
    "payroll.cn.housing_fund_city": {"zh": "公积金城市", "en": "Housing Fund City", "ja": "住宅積立金都市"},
    "payroll.cn.social_insurance_base": {"zh": "社保基数", "en": "SI Base", "ja": "社会保険基数"},
    "payroll.cn.housing_fund_base": {"zh": "公积金基数", "en": "Housing Fund Base", "ja": "住宅積立金基数"},
    "payroll.cn.attendance_salary": {"zh": "出勤工资", "en": "Attendance Salary", "ja": "出勤給与"},
    "payroll.cn.sick_leave_salary": {"zh": "病假工资", "en": "Sick Leave Salary", "ja": "病欠給与"},
    "payroll.cn.attendance_days": {"zh": "出勤天数", "en": "Attendance Days", "ja": "出勤日数"},
    "payroll.cn.full_attendance_bonus": {"zh": "全勤奖", "en": "Full Attendance Bonus", "ja": "皆勤手当"},
    "payroll.cn.other_allowance": {"zh": "其他加项", "en": "Other Allowance", "ja": "その他手当"},
    "payroll.cn.other_deduction": {"zh": "其他扣款", "en": "Other Deduction", "ja": "その他控除"},
    "payroll.cn.social_insurance_employee": {"zh": "社保(个人)", "en": "SI (Employee)", "ja": "社会保険(本人)"},
    "payroll.cn.social_insurance_employer": {"zh": "社保(单位)", "en": "SI (Employer)", "ja": "社会保険(会社)"},
    "payroll.cn.housing_fund_employee": {"zh": "公积金(个人)", "en": "Housing Fund (Employee)", "ja": "住宅積立金(本人)"},
    "payroll.cn.housing_fund_employer": {"zh": "公积金(单位)", "en": "Housing Fund (Employer)", "ja": "住宅積立金(会社)"},
    "payroll.cn.income_tax": {"zh": "个税", "en": "Income Tax", "ja": "所得税"},
    "payroll.cn.net_pay": {"zh": "实发工资", "en": "Net Pay", "ja": "差引支給額"},
    "payroll.cn.employer_cost": {"zh": "雇主成本", "en": "Employer Cost", "ja": "雇主コスト"},
    "payroll.cn.total_earnings": {"zh": "收入 / Earnings", "en": "Income / Earnings", "ja": "収入 / Earnings"},
    "payroll.cn.total_deductions": {"zh": "扣除 / Deductions", "en": "Deductions", "ja": "控除 / Deductions"},
    "payroll.cn.annual_leave": {"zh": "年假", "en": "Annual Leave", "ja": "年次有給休暇"},
    "payroll.cn.sick_leave": {"zh": "病假", "en": "Sick Leave", "ja": "病欠"},
    "payroll.cn.personal_leave": {"zh": "事假", "en": "Personal Leave", "ja": "私用休暇"},
    "payroll.cn.other_leave": {"zh": "其他假", "en": "Other Leave", "ja": "その他休暇"},
    "payroll.cn.full_attendance_days": {"zh": "满勤天数", "en": "Full Attendance Days", "ja": "皆勤日数"},
    "payroll.cn.attendance_label": {"zh": "出勤 / Attendance", "en": "Attendance", "ja": "出勤"},
    "payroll.cn.calc_completed": {"zh": "计算完成", "en": "Calculation completed", "ja": "計算が完了しました"},
    "payroll.cn.confirmed": {"zh": "已定稿", "en": "Finalized", "ja": "確定済み"},
    "payroll.cn.voided": {"zh": "已作废", "en": "Voided", "ja": "無効化済み"},
    "payroll.cn.deleted": {"zh": "已删除", "en": "Deleted", "ja": "削除済み"},
    "payroll.cn.rolled_back": {"zh": "已回退", "en": "Rolled Back", "ja": "ロールバック済み"},
    "payroll.cn.recalculated": {"zh": "已重新计算", "en": "Recalculated", "ja": "再計算済み"},
    "payroll.cn.record_updated": {"zh": "记录已更新", "en": "Record updated", "ja": "レコードを更新しました"},
    "payroll.cn.manually_edited": {"zh": "已手动编辑", "en": "Manually Edited", "ja": "手動編集済み"},
    "payroll.cn.confirm_calc": {"zh": "确认计算", "en": "Confirm Calculation", "ja": "計算確認"},
    "payroll.cn.confirm_finalize": {"zh": "确认定稿", "en": "Confirm Finalize", "ja": "確定確認"},
    "payroll.cn.confirm_rollback": {"zh": "确认回退", "en": "Confirm Rollback", "ja": "ロールバック確認"},
    "payroll.cn.confirm_delete": {"zh": "确认删除", "en": "Confirm Delete", "ja": "削除確認"},
    "payroll.cn.calc_warning": {"zh": "计算将覆盖所有当前数据，确定继续？", "en": "Calculation will overwrite all current data. Continue?", "ja": "計算により現在のデータが上書きされます。続行しますか？"},
    "payroll.cn.finalize_warning": {"zh": "定稿后将生成工资单，确定继续？", "en": "Payslips will be generated after finalization. Continue?", "ja": "確定後に給与明細が生成されます。続行しますか？"},
    "payroll.cn.delete_warning": {"zh": "确定删除此批次吗？此操作不可撤销。", "en": "Delete this batch? This action cannot be undone.", "ja": "このバッチを削除しますか？この操作は取り消せません。"},
    "payroll.cn.rollback_reason_required": {"zh": "请输入回退原因", "en": "Please enter rollback reason", "ja": "ロールバック理由を入力してください"},
    "payroll.cn.rollback_reason_placeholder": {"zh": "请输入回退原因...", "en": "Enter rollback reason...", "ja": "ロールバック理由を入力..."},
    "payroll.cn.rollback_batch": {"zh": "回退批次", "en": "Rollback Batch", "ja": "バッチロールバック"},
    "payroll.cn.beijing": {"zh": "北京 (110000)", "en": "Beijing (110000)", "ja": "北京 (110000)"},
    "payroll.cn.shanghai": {"zh": "上海 (310000)", "en": "Shanghai (310000)", "ja": "上海 (310000)"},
    "payroll.cn.nanjing": {"zh": "南京 (320100)", "en": "Nanjing (320100)", "ja": "南京 (320100)"},
    "payroll.cn.changchun": {"zh": "长春 (220100)", "en": "Changchun (220100)", "ja": "長春 (220100)"},
    "payroll.cn.branch_name": {"zh": "支行名称", "en": "Branch Name", "ja": "支店名"},

    # ── Payroll Email Settings (shared) ──
    "payroll.email.sender_name": {"zh": "发件人名称", "en": "Sender Name", "ja": "送信者名"},
    "payroll.email.sender_email": {"zh": "发件人邮箱", "en": "Sender Email", "ja": "送信者メール"},
    "payroll.email.sender_info_hint": {"zh": "发送工资单时显示的发件人信息。", "en": "Sender information displayed when sending payslips.", "ja": "給与明細送信時に表示される送信者情報。"},
    "payroll.email.placeholder_sender_name": {"zh": "例：TACAI Payroll JP", "en": "e.g. TACAI Payroll JP", "ja": "例：TACAI Payroll JP"},
    "payroll.email.placeholder_sender_email": {"zh": "例：payroll@yourcompany.com", "en": "e.g. payroll@yourcompany.com", "ja": "例：payroll@yourcompany.com"},
    "payroll.email.cc_hint": {"zh": "每封工资单邮件都会抄送到以下邮箱（HR、财务等需要留档的部门）。", "en": "Each payslip email will be CC'd to the following addresses (HR, Finance, etc.).", "ja": "各給与明細メールは以下のアドレスにCC送信されます（HR、経理など記録保管が必要な部門）。"},
    "payroll.email.no_cc": {"zh": "暂无抄送人，工资单仅发送给员工本人。", "en": "No CC recipients. Payslips will be sent to employees only.", "ja": "CC受信者がいません。給与明細は従業員本人のみに送信されます。"},
    "payroll.email.email_template": {"zh": "邮件模版", "en": "Email Template", "ja": "メールテンプレート"},
    "payroll.email.template_hint": {"zh": "设置邮件主题、正文顶部/底部内容，以及工资单上显示的项目。", "en": "Configure email subject, header/footer content, and payslip display items.", "ja": "メール件名、本文のヘッダー/フッター、および給与明細の表示項目を設定します。"},
    "payroll.email.subject_label": {"zh": "📌 邮件主题", "en": "📌 Email Subject", "ja": "📌 メール件名"},
    "payroll.email.subject_placeholder": {"zh": "留空使用默认格式：給与明細 / Payslip — 月份 — 员工姓名", "en": "Leave empty for default: Payslip — Month — Employee Name", "ja": "空欄の場合デフォルト形式：給与明細 — 月 — 社員名"},
    "payroll.email.reset_default": {"zh": "恢复默认", "en": "Reset Default", "ja": "デフォルトに戻す"},
    "payroll.email.clear": {"zh": "清空", "en": "Clear", "ja": "クリア"},
    "payroll.email.header_placeholder": {"zh": "例：<p>各位员工，请查收本月工资单。如有疑问请联系HR。</p>", "en": "e.g. <p>Dear employees, please find your payslip. Contact HR for questions.</p>", "ja": "例：<p>各位従業員各位、今月の給与明細をご確認ください。ご不明な点はHRまでお問い合わせください。</p>"},
    "payroll.email.footer_placeholder": {"zh": "例：<p style=\"color:#888\">此邮件由系统自动发送。如有疑问请联系 HR。</p>", "en": "e.g. <p style=\"color:#888\">This email is auto-generated. Contact HR for questions.</p>", "ja": "例：<p style=\"color:#888\">このメールはシステムにより自動送信されています。ご不明な点はHRまでお問い合わせください。</p>"},
    "payroll.email.payslip_items_label": {"zh": "📄 工资单显示项目", "en": "📄 Payslip Display Items", "ja": "📄 給与明細表示項目"},
    "payroll.email.items_hint": {"zh": "勾选要显示的项目。默认值来自<a href=\"{url}\" target=\"_blank\">工资项目定义</a>。", "en": "Select items to display. Defaults from <a href=\"{url}\" target=\"_blank\">Payroll Item Definitions</a>.", "ja": "表示する項目を選択します。デフォルトは<a href=\"{url}\" target=\"_blank\">給与項目定義</a>から取得されます。"},
    "payroll.email.earnings_group": {"zh": "💰 支给项目", "en": "💰 Earnings", "ja": "💰 支給項目"},
    "payroll.email.deductions_group": {"zh": "📉 控除项目", "en": "📉 Deductions", "ja": "📉 控除項目"},
    "payroll.email.employer_cost_group": {"zh": "🏢 会社负担", "en": "🏢 Employer Cost", "ja": "🏢 会社負担"},
    "payroll.email.using_default": {"zh": "使用默认", "en": "Using Default", "ja": "デフォルト使用"},
    "payroll.email.customized": {"zh": "已自定义", "en": "Customized", "ja": "カスタマイズ済"},
    "payroll.email.test_email_title": {"zh": "发送测试邮件", "en": "Send Test Email", "ja": "テストメール送信"},
    "payroll.email.test_email_hint": {"zh": "用当前设置发送一封测试邮件到指定邮箱，确认配置正确。", "en": "Send a test email with current settings to verify configuration.", "ja": "現在の設定でテストメールを指定アドレスに送信し、設定が正しいか確認します。"},
    "payroll.email.recipient_email": {"zh": "收件人邮箱", "en": "Recipient Email", "ja": "受信者メール"},
    "payroll.email.send_test": {"zh": "发送测试", "en": "Send Test", "ja": "テスト送信"},
    "payroll.email.test_sent": {"zh": "✅ 测试邮件已发送，请检查收件箱", "en": "✅ Test email sent. Please check inbox.", "ja": "✅ テストメールを送信しました。受信トレイを確認してください。"},
    "payroll.email.smtp_advanced": {"zh": "SMTP 高级设置", "en": "SMTP Advanced", "ja": "SMTP詳細設定"},
    "payroll.email.smtp_server": {"zh": "服务器", "en": "Server", "ja": "サーバー"},
    "payroll.email.smtp_server_hint": {"zh": "邮件服务商的 SMTP 服务器域名。系统SMTP已配置时无需填写。", "en": "SMTP server hostname. Leave empty if system SMTP is configured.", "ja": "メールサービスプロバイダのSMTPサーバー。システムSMTP設定済みの場合は不要です。"},
    "payroll.email.smtp_port": {"zh": "端口", "en": "Port", "ja": "ポート"},
    "payroll.email.smtp_port_hint": {"zh": "通常是 587", "en": "Usually 587", "ja": "通常は587"},
    "payroll.email.smtp_user": {"zh": "邮箱账号", "en": "Email Account", "ja": "メールアカウント"},
    "payroll.email.smtp_user_hint": {"zh": "通常是发件邮箱地址", "en": "Usually the sender email address", "ja": "通常は送信者メールアドレス"},
    "payroll.email.smtp_password": {"zh": "授权码 / 密码", "en": "Auth Code / Password", "ja": "認証コード / パスワード"},
    "payroll.email.smtp_password_hint": {"zh": "邮箱授权码（非登录密码）", "en": "Email auth code (not login password)", "ja": "メール認証コード（ログインパスワードではありません）"},
    "payroll.email.smtp_tls_hint": {"zh": "端口 587 时通常开启，端口 465 时关闭（用SSL）", "en": "Enable for port 587, disable for port 465 (SSL)", "ja": "ポート587の場合は有効、ポート465(SSL)の場合は無効"},
    "payroll.email.password_set": {"zh": "已设置", "en": "Set", "ja": "設定済み"},
    "payroll.email.change_password": {"zh": "修改", "en": "Change", "ja": "変更"},
    "payroll.email.using_system_smtp": {"zh": "当前使用系统SMTP服务器发送邮件，一般无需修改。", "en": "Currently using system SMTP server. No changes needed.", "ja": "現在システムSMTPサーバーを使用してメールを送信中です。通常は変更不要です。"},
    "payroll.email.smtp_not_configured": {"zh": "系统SMTP未配置，请填写以下信息以启用邮件发送。", "en": "System SMTP not configured. Fill in the following to enable email sending.", "ja": "システムSMTPが未設定です。メール送信を有効にするには以下の情報を入力してください。"},
    "payroll.email.preview": {"zh": "📧 邮件预览", "en": "📧 Email Preview", "ja": "📧 メールプレビュー"},
    "payroll.email.preview_unavailable": {"zh": "无法加载预览", "en": "Preview Unavailable", "ja": "プレビューを読み込めません"},
    "payroll.email.validate_sender_name_required": {"zh": "请输入发件人名称", "en": "Please enter sender name", "ja": "送信者名を入力してください"},
    "payroll.email.validate_sender_email_required": {"zh": "请输入发件人邮箱", "en": "Please enter sender email", "ja": "送信者メールを入力してください"},
    "payroll.email.validate_sender_email_format": {"zh": "请输入有效的邮箱地址", "en": "Please enter a valid email", "ja": "有効なメールアドレスを入力してください"},
    "payroll.email.validate_email_format": {"zh": "邮箱格式不正确", "en": "Invalid email format", "ja": "メール形式が正しくありません"},
    "payroll.email.validate_sender_email_invalid": {"zh": "发件人邮箱格式不正确", "en": "Invalid sender email format", "ja": "送信者メール形式が正しくありません"},
    "payroll.email.validate_smtp_required": {"zh": "请先配置 SMTP。展开「SMTP 高级设置」填写服务器信息，或联系管理员配置环境变量。", "en": "Please configure SMTP first. Expand SMTP Advanced Settings or contact admin.", "ja": "先にSMTPを設定してください。「SMTP詳細設定」を展開するか、管理者に連絡して環境変数を設定してください。"},
    "payroll.email.validate_smtp_user_required": {"zh": "SMTP 邮箱账号为必填", "en": "SMTP email account is required", "ja": "SMTPメールアカウントは必須です"},
    "payroll.email.validate_smtp_password_required": {"zh": "SMTP 授权码为必填", "en": "SMTP auth code is required", "ja": "SMTP認証コードは必須です"},
    "payroll.email.validate_test_recipient_required": {"zh": "请输入收件人邮箱", "en": "Please enter recipient email", "ja": "受信者メールを入力してください"},
    "payroll.email.cc_duplicate": {"zh": "已在CC列表中", "en": "Already in CC list", "ja": "既にCCリストに追加済み"},

    # ── Payroll Payslips (shared) ──
    "payroll.payslip.send_log": {"zh": "📋 邮件发送日志", "en": "📋 Email Send Log", "ja": "📋 メール送信ログ"},
    "payroll.payslip.sent_at": {"zh": "发送时间", "en": "Sent At", "ja": "送信日時"},
    "payroll.payslip.recipient": {"zh": "收件人", "en": "Recipient", "ja": "受信者"},
    "payroll.payslip.operator": {"zh": "操作人", "en": "Operator", "ja": "操作者"},
    "payroll.payslip.error_reason": {"zh": "失败原因", "en": "Error Reason", "ja": "エラー理由"},
    "payroll.payslip.no_logs": {"zh": "暂无发送记录", "en": "No send records", "ja": "送信記録なし"},
    "payroll.payslip.records_count": {"zh": "{count} 条记录", "en": "{count} records", "ja": "{count}件の記録"},
    "payroll.payslip.pending_count": {"zh": "{count} 封待发送", "en": "{count} pending", "ja": "{count}件送信待ち"},
    "payroll.payslip.smtp_notice": {"zh": "⚠️ 前往<router-link to=\"{url}\">邮件设置</router-link>配置SMTP后即可发送", "en": "⚠️ Go to <router-link to=\"{url}\">Email Settings</router-link> to configure SMTP", "ja": "⚠️ <router-link to=\"{url}\">メール設定</router-link>でSMTPを設定すると送信可能になります"},
    "payroll.payslip.send_all": {"zh": "📨 一键发送全部", "en": "📨 Send All", "ja": "📨 一括送信"},
    "payroll.payslip.send_all_n": {"zh": "📨 一键发送全部（{n}封）", "en": "📨 Send All ({n})", "ja": "📨 一括送信（{n}通）"},
    "payroll.payslip.confirm_send_n": {"zh": "确认发送 {n} 封工资单邮件？已发送过的将自动跳过。", "en": "Send {n} payslip emails? Already-sent will be skipped.", "ja": "{n}通の給与明細メールを送信しますか？送信済みは自動スキップされます。"},
    "payroll.payslip.send_all_title": {"zh": "一键发送全部", "en": "Send All", "ja": "一括送信"},
    "payroll.payslip.send": {"zh": "发送", "en": "Send", "ja": "送信"},
    "payroll.payslip.success": {"zh": "✅ 成功", "en": "✅ Success", "ja": "✅ 成功"},
    "payroll.payslip.failed": {"zh": "❌ 失败", "en": "❌ Failed", "ja": "❌ 失敗"},
    "payroll.payslip.needs_smtp_tooltip": {"zh": "请先在邮件设置中配置SMTP", "en": "Please configure SMTP in Email Settings first", "ja": "先にメール設定でSMTPを設定してください"},
    "payroll.payslip.close": {"zh": "关闭", "en": "Close", "ja": "閉じる"},

    # ── Payroll CN Batch Detail columns ──
    "payroll.cn.col_employee_no": {"zh": "编号", "en": "No.", "ja": "番号"},
    "payroll.cn.col_name": {"zh": "姓名", "en": "Name", "ja": "氏名"},
    "payroll.cn.col_actions": {"zh": "操作", "en": "Actions", "ja": "操作"},
    "payroll.cn.edit": {"zh": "编辑", "en": "Edit", "ja": "編集"},
    "payroll.cn.recalc": {"zh": "重算", "en": "Recalc", "ja": "再計算"},
    "payroll.cn.calculate": {"zh": "🧮 计算", "en": "🧮 Calculate", "ja": "🧮 計算"},
    "payroll.cn.finalize": {"zh": "✅ 定稿", "en": "✅ Finalize", "ja": "✅ 確定"},
    "payroll.cn.rollback": {"zh": "↩️ 回退", "en": "↩️ Rollback", "ja": "↩️ ロールバック"},
    "payroll.cn.void": {"zh": "🚫 作废", "en": "🚫 Void", "ja": "🚫 無効化"},
    "payroll.cn.audit_log": {"zh": "📋 审计日志", "en": "📋 Audit Log", "ja": "📋 監査ログ"},
    "payroll.cn.employee_count": {"zh": "员工数", "en": "Employee Count", "ja": "社員数"},
    "payroll.cn.gross_total": {"zh": "应发合计", "en": "Gross Total", "ja": "総支給合計"},
    "payroll.cn.deduction_total": {"zh": "扣除合计", "en": "Deduction Total", "ja": "控除合計"},
    "payroll.cn.net_total": {"zh": "实发合计", "en": "Net Total", "ja": "差引支給合計"},
    "payroll.cn.net_pay_label": {"zh": "实发工资:", "en": "Net Pay:", "ja": "差引支給額:"},
    "payroll.cn.gross_total_label": {"zh": "应发合计:", "en": "Gross Total:", "ja": "総支給合計:"},
    "payroll.cn.deduction_total_label": {"zh": "扣除合计:", "en": "Deduction Total:", "ja": "控除合計:"},
    "payroll.cn.no_audit_logs": {"zh": "暂无审计记录", "en": "No audit records", "ja": "監査記録なし"},

    # ── Payroll CN search placeholder ──
    "payroll.cn.search_placeholder": {"zh": "搜索姓名/编号...", "en": "Search name/no...", "ja": "氏名/番号で検索..."},

    # ── Payroll JP item definitions ──
    "payroll.jp.social_insurance_calc_base": {"zh": "社会保険算定基礎", "en": "SI Calc Base", "ja": "社会保険算定基礎"},
    "payroll.jp.employment_insurance_calc_base": {"zh": "雇用保険算定基礎", "en": "EI Calc Base", "ja": "雇用保険算定基礎"},
}


def add_keys_to_json():
    """Add all NEW_KEYS to all three language JSON files."""
    for lang in ['en', 'ja', 'zh']:
        path = os.path.join(I18N_DIR, f'{lang}.json')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        added = 0
        for key, vals in NEW_KEYS.items():
            if key not in data:
                data[key] = vals[lang]
                added += 1

        # Sort keys alphabetically
        sorted_data = dict(sorted(data.items(), key=lambda x: x[0]))

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(sorted_data, f, indent=2, ensure_ascii=False)
            f.write('\n')

        print(f'{lang}.json: {len(sorted_data)} keys ({added} added)')


if __name__ == '__main__':
    add_keys_to_json()
    print(f'\nTotal new keys added: {len(NEW_KEYS)}')
