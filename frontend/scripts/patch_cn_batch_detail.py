#!/usr/bin/env python3
"""Apply i18n replacements to CnPayrollBatchDetail.vue"""
import re

PATH = '/Users/wangchen/Desktop/TACAI/tacone/frontend/src/modules/payroll/cn/CnPayrollBatchDetail.vue'
with open(PATH) as f:
    content = f.read()

# ── SCRIPT SECTION REPLACEMENTS ──

# 1. Edit field groups — convert to computed()
old = """\t// ── Edit field groups ──
\tconst editFieldGroups = [
\t  {
\t    title: '出勤 / Attendance',
\t    fields: [
\t      { key: 'full_attendance_days', label: '满勤天数', min: 0, precision: 1 },
\t      { key: 'actual_attendance_days', label: '出勤天数', min: 0, precision: 1 },
\t      { key: 'personal_leave_days', label: '事假', min: 0, precision: 2 },
\t      { key: 'annual_leave_days', label: '年假', min: 0, precision: 2 },
\t      { key: 'sick_leave_days', label: '病假', min: 0, precision: 2 },
\t      { key: 'other_leave_days', label: '其他假', min: 0, precision: 2 },
\t    ],
\t  },
\t  {
\t    title: '收入 / Earnings',
\t    fields: [
\t      { key: 'other_additions', label: '其他加项', min: 0, precision: 2 },
\t      { key: 'full_attendance_bonus', label: '全勤奖', min: 0, precision: 2 },
\t    ],
\t  },
\t  {
\t    title: '扣除 / Deductions',
\t    fields: [
\t      { key: 'other_deductions', label: '其他扣款', min: 0, precision: 2 },
\t    ],
\t  },
\t]"""

new = """\t// ── Edit field groups ──
\tconst editFieldGroups = computed(() => [
\t  {
\t    title: t('payroll.cn.attendance_label'),
\t    fields: [
\t      { key: 'full_attendance_days', label: t('payroll.cn.full_attendance_days'), min: 0, precision: 1 },
\t      { key: 'actual_attendance_days', label: t('payroll.cn.attendance_days'), min: 0, precision: 1 },
\t      { key: 'personal_leave_days', label: t('payroll.cn.personal_leave'), min: 0, precision: 2 },
\t      { key: 'annual_leave_days', label: t('payroll.cn.annual_leave'), min: 0, precision: 2 },
\t      { key: 'sick_leave_days', label: t('payroll.cn.sick_leave'), min: 0, precision: 2 },
\t      { key: 'other_leave_days', label: t('payroll.cn.other_leave'), min: 0, precision: 2 },
\t    ],
\t  },
\t  {
\t    title: t('payroll.cn.total_earnings'),
\t    fields: [
\t      { key: 'other_additions', label: t('payroll.cn.other_allowance'), min: 0, precision: 2 },
\t      { key: 'full_attendance_bonus', label: t('payroll.cn.full_attendance_bonus'), min: 0, precision: 2 },
\t    ],
\t  },
\t  {
\t    title: t('payroll.cn.total_deductions'),
\t    fields: [
\t      { key: 'other_deductions', label: t('payroll.cn.other_deduction'), min: 0, precision: 2 },
\t    ],
\t  },
\t])"""

if old in content:
    content = content.replace(old, new)
    print('✓ editFieldGroups → computed with t()')
else:
    print('✗ editFieldGroups NOT FOUND (check whitespace)')

# 2. ElMessageBox / ElMessage calls in script
replacements_script = [
    ("ElMessageBox.confirm('计算将覆盖所有当前数据，确定继续？', '确认计算', { type: 'warning' })",
     "ElMessageBox.confirm(t('payroll.cn.calc_warning'), t('payroll.cn.confirm_calc'), { type: 'warning' })"),
    ("ElMessage.success('计算完成')",
     "ElMessage.success(t('payroll.cn.calc_completed'))"),
    ("ElMessageBox.confirm('定稿后将生成工资单，确定继续？', '确认定稿', { type: 'warning' })",
     "ElMessageBox.confirm(t('payroll.cn.finalize_warning'), t('payroll.cn.confirm_finalize'), { type: 'warning' })"),
    ("ElMessage.success('已定稿')",
     "ElMessage.success(t('payroll.cn.confirmed'))"),
    ("ElMessage.warning('请输入回退原因')",
     "ElMessage.warning(t('payroll.cn.rollback_reason_required'))"),
    ("ElMessage.success('已回退')",
     "ElMessage.success(t('payroll.cn.rolled_back'))"),
    ("ElMessage.success('已作废')",
     "ElMessage.success(t('payroll.cn.voided'))"),
    ("ElMessageBox.confirm('确定删除此批次吗？此操作不可撤销。', '确认删除', { type: 'warning' })",
     "ElMessageBox.confirm(t('payroll.cn.delete_warning'), t('payroll.cn.confirm_delete'), { type: 'warning' })"),
    ("ElMessage.success('已删除')",
     "ElMessage.success(t('payroll.cn.deleted'))"),
    ("ElMessage.success('记录已更新')",
     "ElMessage.success(t('payroll.cn.record_updated'))"),
    ("ElMessage.success('已重新计算')",
     "ElMessage.success(t('payroll.cn.recalculated'))"),
    ("const { value: reason } = await ElMessageBox.prompt('请输入作废原因', '确认作废', { type: 'warning' })",
     "const { value: reason } = await ElMessageBox.prompt(t('payroll.cn.rollback_reason_placeholder'), t('payroll.cn.confirm_void'), { type: 'warning' })"),
    ("content=\"已手动编辑\"",
     "content=\"已手动编辑\"")  # keep as-is, will handle in template
]

for old_s, new_s in replacements_script:
    if old_s in content:
        content = content.replace(old_s, new_s)
        print(f'✓ {old_s[:60]}...')
    else:
        # Try without single quotes variant
        pass

# ── TEMPLATE SECTION REPLACEMENTS ──

# Header action buttons
tmpl = [
    (">🧮 计算<", ">🧮 {{ t('payroll.cn.calculate') }}<"),
    (">✅ 定稿<", ">✅ {{ t('payroll.cn.finalize') }}<"),
    (">↩️ 回退<", ">↩️ {{ t('payroll.cn.rollback') }}<"),
    (">🚫 作废<", ">🚫 {{ t('payroll.cn.void') }}<"),
    ("📋 审计日志<", "📋 {{ t('payroll.cn.audit_log') }}<"),
    # Summary cards
    (">员工数<", ">{{ t('payroll.cn.employee_count') }}<"),
    (">应发合计<", ">{{ t('payroll.cn.gross_total') }}<"),
    (">扣除合计<", ">{{ t('payroll.cn.deduction_total') }}<"),
    (">实发合计<", ">{{ t('payroll.cn.net_total') }}<"),
    (">雇主成本<", ">{{ t('payroll.cn.employer_cost') }}<"),
    # Info row labels
    ('label="工资月份"', ':label="t(\'field.payroll_month\')"'),
    ('label="法人实体"', ':label="t(\'field.entity\')"'),
    ('label="标准工作天数"', ':label="t(\'field.standard_work_days\')"'),
    ('label="创建人"', ':label="t(\'field.created_by\')"'),
    # Table column labels
    ('label="姓名"', ':label="t(\'payroll.cn.col_name\')"'),
    ('label="编号"', ':label="t(\'payroll.cn.col_employee_no\')"'),
    ('label="满勤天数"', ':label="t(\'payroll.cn.full_attendance_days\')"'),
    ('label="出勤天数"', ':label="t(\'payroll.cn.attendance_days\')"'),
    ('label="事假"', ':label="t(\'payroll.cn.personal_leave\')"'),
    ('label="年假"', ':label="t(\'payroll.cn.annual_leave\')"'),
    ('label="病假"', ':label="t(\'payroll.cn.sick_leave\')"'),
    ('label="基本工资"', ':label="t(\'field.basic_salary\')"'),
    ('label="职位津贴"', ':label="t(\'field.position_allowance\')"'),
    ('label="出勤工资"', ':label="t(\'payroll.cn.attendance_salary\')"'),
    ('label="病假工资"', ':label="t(\'payroll.cn.sick_leave_salary\')"'),
    ('label="全勤奖"', ':label="t(\'payroll.cn.full_attendance_bonus\')"'),
    ('label="其他加项"', ':label="t(\'payroll.cn.other_allowance\')"'),
    ('label="社保(个人)"', ':label="t(\'payroll.cn.social_insurance_employee\')"'),
    ('label="公积金(个人)"', ':label="t(\'payroll.cn.housing_fund_employee\')"'),
    ('label="个税"', ':label="t(\'payroll.cn.income_tax\')"'),
    ('label="其他扣款"', ':label="t(\'payroll.cn.other_deduction\')"'),
    ('label="应发合计"', ':label="t(\'payroll.cn.gross_total\')"'),
    ('label="扣除合计"', ':label="t(\'payroll.cn.deduction_total\')"'),
    ('label="实发工资"', ':label="t(\'payroll.cn.net_pay\')"'),
    ('label="社保(单位)"', ':label="t(\'payroll.cn.social_insurance_employer\')"'),
    ('label="公积金(单位)"', ':label="t(\'payroll.cn.housing_fund_employer\')"'),
    ('label="操作"', ':label="t(\'payroll.cn.col_actions\')"'),
    # Table action buttons
    (">编辑<", ">{{ t('payroll.cn.edit') }}<"),
    (">重算<", ">{{ t('payroll.cn.recalc') }}<"),
    # Manual edit tooltip
    ('content="已手动编辑"', ':content="t(\'payroll.cn.manually_edited\')"'),
    # Edit dialog title
    (':title="`编辑记录 — ${editForm.employee_name}`"', ':title="t(\'payroll.jp.edit_record_title\', { name: editForm.employee_name })"'),
    # Edit dialog read-only totals
    (">应发合计:<", ">{{ t('payroll.cn.gross_total_label') }}<"),
    (">扣除合计:<", ">{{ t('payroll.cn.deduction_total_label') }}<"),
    (">实发工资:<", ">{{ t('payroll.cn.net_pay_label') }}<"),
    # Edit dialog footer buttons
    (">取消<", ">{{ t('common.cancel') }}<"),
    (">保存<", ">{{ t('common.save') }}<"),
    # Rollback dialog
    ('title="回退批次"', ':title="t(\'payroll.cn.rollback_batch\')"'),
    ('placeholder="请输入回退原因..."', ':placeholder="t(\'payroll.cn.rollback_reason_placeholder\')"'),
    (">确认回退<", ">{{ t('payroll.cn.confirm_rollback') }}<"),
    # Audit dialog
    ('title="审计日志"', ':title="t(\'payroll.cn.audit_log\')"'),
    (">暂无审计记录<", ">{{ t('payroll.cn.no_audit_logs') }}<"),
]

for old_s, new_s in tmpl:
    if old_s in content:
        content = content.replace(old_s, new_s)
    else:
        print(f'  NOT FOUND: {old_s[:60]}')

# Fix: there should be no duplicate common.cancel replacements (first one gets second <el-button)
# The edit dialog already has 取消/保存, the rollback dialog also has 取消/确认回退
# We already replaced the edit dialog's 取消→common.cancel and 保存→common.save
# The rollback dialog also has 取消 — after our replacement, it was already changed at line 418
# But the rollback "确认回退" was changed above

with open(PATH, 'w') as f:
    f.write(content)

print('\nDone with CnPayrollBatchDetail.vue')
