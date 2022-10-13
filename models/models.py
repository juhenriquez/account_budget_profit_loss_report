# -*- coding: utf-8 -*-

import calendar
from odoo import models, fields, api, _

import copy
import ast

import calendar
from datetime import *
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, ustr
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


MONTHS = [(str(i), calendar.month_name[i]) for i in range(1,13)]
YEARS = [(str(i), str(i)) for i in range(2000,2100)]

def get_months_from_dates(date_from, date_to):
    date1 = datetime.strptime(date_from, "%Y-%m-%d")
    date2 = datetime.strptime(date_to, "%Y-%m-%d")
    date1 = date1.replace(day = 1)
    date2 = date2.replace(day = 1)
    months_str = calendar.month_name
    months = []
    while date1 < date2:
        month = date1.month
        year  = date1.year
        month_str = months_str[month][0:3]
        months.append((str(month),str(year)))
        next_month = month+1 if month != 12 else 1
        next_year = year + 1 if next_month == 1 else year
        date1 = date1.replace( month = next_month, year= next_year)

    return months

class BudgetAccountFiscalConfig(models.Model):

    _name = "account.budget.fiscal.config"
    _rec_name = "fiscal_year_id"

    @api.depends("budget_line.budget_subtotal")
    def _compute_budget_amount_total(self):
        for config in self:
            budget_amount_total = float()
            for line in config.budget_line:
                budget_amount_total += line.budget_subtotal

            config.update({
                    'budget_amount_total':budget_amount_total,
                })


    fiscal_year_id = fields.Many2one("account.fiscal.year", "Fiscal Year", required=True)
    budget_line = fields.One2many('account.budget.fiscal.config.line', 'budget_fiscal_config_id', string='Budget Lines', copy=True, auto_join=True)
    budget_amount_total = fields.Monetary(string='Total Budget', store=True, readonly=True, tracking=4, compute="_compute_budget_amount_total")
    currency_id = fields.Many2one("res.currency", "Currency")

class BudgetAccountFiscalConfigLine(models.Model):

    _name = "account.budget.fiscal.config.line"

    @api.depends("budget_account_line.amount_budget")
    def _compute_budget_subtotal(self):
        for config_line in self:
            budget_subtotal = float()
            for line in config_line.budget_account_line:
                budget_subtotal += line.amount_budget
            config_line.update({
                    'budget_subtotal':budget_subtotal,
                })

    budget_fiscal_config_id = fields.Many2one('account.budget.fiscal.config', string='Budget Config', required=True, ondelete='cascade', index=True, copy=False)
    month = fields.Selection(MONTHS, "Month", required=True)
    year = fields.Selection(YEARS, "Year", required=True)
    budget_account_line = fields.One2many('account.budget.fiscal.account.line', 'config_line_id', string='Budget Lines', copy=True, auto_join=True)
    budget_subtotal = fields.Monetary("Budget Subtotal", compute="_compute_budget_subtotal")
    currency_id = fields.Many2one("res.currency", "Currency", related="budget_fiscal_config_id.currency_id")

class BudgetAccountFiscalAccountConfigLine(models.Model):

    _name = "account.budget.fiscal.account.line"

    config_line_id = fields.Many2one('account.budget.fiscal.config.line', string='Budget Config', required=True, ondelete='cascade', index=True, copy=False)
    account_id = fields.Many2one('account.account', required=True)
    currency_id = fields.Many2one("res.currency", "Currency", related="config_line_id.currency_id")
    amount_budget = fields.Monetary(string='Total', store=True, readonly=False, tracking=4)

    def _get_budget_for_account(self, date_from, date_to, account_id=False):
        budget = 0.0
        if not account_id:
            return budget
        for account_line in self.search([('account_id','=', account_id)]):
            months_range = get_months_from_dates(date_from, date_to)
            config_line_id = account_line.config_line_id
            for ranges in months_range:
                if config_line_id.month == ranges[0] and config_line_id.year == ranges[1]:
                    budget += account_line.amount_budget
        return budget

class ReportAccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"


    def _get_lines(self, options, line_id=None):
        res = super(ReportAccountFinancialReport, self)._get_lines(options=options, line_id=line_id)
        for x in res:
            if x.get('account_id'):
                date_from = self._context.get('date_from')
                date_to = self._context.get('date_to')
                budget = self.env['account.budget.fiscal.account.line'].with_context(self._context)._get_budget_for_account(date_from, date_to, account_id=x.get('account_id'))
                budget_formatted = formatLang(self.env, budget, currency_obj=self.env.company.currency_id)
                report_val = x.get('columns')[0].get('no_format_name')
                over_budget =  report_val - budget
                over_budget_formatted = formatLang(self.env, over_budget, currency_obj=self.env.company.currency_id)
                over_budget_percent = 0
                if budget > 0:
                    over_budget_percent = round((report_val / budget) * 100, 2)
                x.get('columns').insert(0, {'name':budget_formatted, 'no_format_name':budget})
                x.get('columns').append({'name':over_budget_formatted, 'no_format_name':over_budget_formatted})
                x.get('columns').append({'name':"{} %".format(over_budget_percent), 'no_format_name':"{} %".format(over_budget_percent)})
            else:
                x.get('columns').insert(0, {'name':''})
                x.get('columns').append({'name':''})
                x.get('columns').append({'name':''})
        return res

    def _get_columns_name(self, options):
        columns = [{'name': ''}, {'name':'Budget'}]
        if self.debit_credit and not options.get('comparison', {}).get('periods', False):
            columns += [{'name': _('Debit'), 'class': 'number'}, {'name': _('Credit'), 'class': 'number'}]
        if not self.filter_date:
            if self.date_range:
                self.filter_date = {'mode': 'range', 'filter': 'this_year'}
            else:
                self.filter_date = {'mode': 'single', 'filter': 'today'}
        columns += [{'name': self.format_date(options), 'class': 'number'}]
        if options.get('comparison') and options['comparison'].get('periods'):
            for period in options['comparison']['periods']:
                columns += [{'name': period.get('string'), 'class': 'number'}]
            if options['comparison'].get('number_period') == 1 and not options.get('groups'):
                columns += [{'name': '%', 'class': 'number'}]

        if options.get('groups', {}).get('ids'):
            columns_for_groups = []
            for column in columns[1:]:
                for ids in options['groups'].get('ids'):
                    group_column_name = ''
                    for index, id in enumerate(ids):
                        column_name = self._get_column_name(id, options['groups']['fields'][index])
                        group_column_name += ' ' + column_name
                    columns_for_groups.append({'name': column.get('name') + group_column_name, 'class': 'number'})
            columns = columns[:1] + columns_for_groups
        columns.append({'name':'Over Budget'})
        columns.append({'name':"% of Budget"})
        return columns

class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"

    def _get_lines(self, financial_report, currency_table, options, linesDicts):
        final_result_table = []
        comparison_table = [options.get('date')]
        comparison_table += options.get('comparison') and options['comparison'].get('periods', []) or []
        currency_precision = self.env.company.currency_id.rounding

        # build comparison table
        for line in self:
            res = []
            debit_credit = len(comparison_table) == 1
            domain_ids = {'line'}
            k = 0
            for period in comparison_table:
                date_from = period.get('date_from', False)
                date_to = period.get('date_to', False) or period.get('date', False)
                date_from, date_to, strict_range = line.with_context(date_from=date_from, date_to=date_to)._compute_date_range()

                r = line.with_context(date_from=date_from,
                                      date_to=date_to,
                                      strict_range=strict_range)._eval_formula(financial_report,
                                                                               debit_credit,
                                                                               currency_table,
                                                                               linesDicts[k],
                                                                               groups=options.get('groups'))
                debit_credit = False
                res.extend(r)
                for column in r:
                    domain_ids.update(column)
                k += 1

            res = line._put_columns_together(res, domain_ids)

            are_all_columns_zero = all(float_is_zero(k, precision_rounding=currency_precision) for k in res['line'])
            if line.hide_if_zero and are_all_columns_zero and line.formulas:
                continue

            # Post-processing ; creating line dictionnary, building comparison, computing total for extended, formatting
            vals = {
                'id': line.id,
                'name': line.name,
                'level': line.level,
                'class': 'o_account_reports_totals_below_sections' if self.env.company.totals_below_sections else '',
                'columns': [{'name': l} for l in res['line']],
                'unfoldable': len(domain_ids) > 1 and line.show_domain != 'always',
                'unfolded': line.id in options.get('unfolded_lines', []) or line.show_domain == 'always',
                'page_break': line.print_on_new_page,
            }
            if financial_report.tax_report and line.domain and not line.action_id:
                vals['caret_options'] = 'tax.report.line'

            if line.action_id:
                vals['action_id'] = line.action_id.id
            domain_ids.remove('line')
            lines = [vals]
            groupby = line.groupby or 'aml'
            if line.id in options.get('unfolded_lines', []) or line.show_domain == 'always':
                if line.groupby:
                    domain_ids = sorted(list(domain_ids), key=lambda k: line._get_gb_name(k))
                for domain_id in domain_ids:
                    name = line._get_gb_name(domain_id)
                    if not self.env.context.get('print_mode') or not self.env.context.get('no_format'):
                        name = name[:40] + '...' if name and len(name) >= 45 else name
                    vals = {
                        'id': 'financial_report_group_%s_%s' % (line.id, domain_id),
                        'name': name,
                        'level': line.level,
                        'parent_id': line.id,
                        'columns': [{'name': l} for l in res[domain_id]],
                        'caret_options': groupby == 'account_id' and 'account.account' or groupby,
                        'financial_group_line_id': line.id,
                    }
                    for account in self.env['account.account'].sudo().search([('company_id','=', self.env.company.id)]):
                        if account.display_name == name:
                            vals['account_id'] = account.id

                    if line.financial_report_id.name == 'Aged Receivable':
                        vals['trust'] = self.env['res.partner'].browse([domain_id]).trust
                    lines.append(vals)

                if domain_ids and self.env.company.totals_below_sections:
                    lines.append({
                        'id': 'total_' + str(line.id),
                        'name': _('Total') + ' ' + line.name,
                        'level': line.level,
                        'class': 'o_account_reports_domain_total',
                        'parent_id': line.id,
                        'columns': copy.deepcopy(lines[0]['columns']),
                    })

            for vals in lines:
                if len(comparison_table) == 2 and not options.get('groups'):
                    vals['columns'].append(line._build_cmp(vals['columns'][0]['name'], vals['columns'][1]['name']))
                    for i in [0, 1]:
                        vals['columns'][i] = line._format(vals['columns'][i])
                else:
                    vals['columns'] = [line._format(v) for v in vals['columns']]
                if not line.formulas:
                    vals['columns'] = [{'name': ''} for k in vals['columns']]

            if len(lines) == 1:
                new_lines = line.children_ids._get_lines(financial_report, currency_table, options, linesDicts)
                # Manage 'hide_if_zero' field without formulas.
                # If a line hi 'hide_if_zero' and has no formulas, we have to check the sum of all the columns from its children
                # If all sums are zero, we hide the line
                if line.hide_if_zero and not line.formulas:
                    amounts_by_line = [[col['no_format_name'] for col in new_line['columns']] for new_line in new_lines]
                    amounts_by_column = zip(*amounts_by_line)
                    all_columns_have_children_zero = all(float_is_zero(sum(col), precision_rounding=currency_precision) for col in amounts_by_column)
                    if all_columns_have_children_zero:
                        continue
                if new_lines and line.formulas:
                    if self.env.company.totals_below_sections:
                        divided_lines = self._divide_line(lines[0])
                        result = [divided_lines[0]] + new_lines + [divided_lines[-1]]
                    else:
                        result = [lines[0]] + new_lines
                else:
                    if not new_lines and not lines[0]['unfoldable'] and line.hide_if_empty:
                        lines = []
                    result = lines + new_lines
            else:
                result = lines
            final_result_table += result
        return final_result_table