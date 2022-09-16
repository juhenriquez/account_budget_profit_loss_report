# -*- coding: utf-8 -*-
# from odoo import http


# class AccountBudgetProfitLossReport(http.Controller):
#     @http.route('/account_budget_profit_loss_report/account_budget_profit_loss_report/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_budget_profit_loss_report/account_budget_profit_loss_report/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_budget_profit_loss_report.listing', {
#             'root': '/account_budget_profit_loss_report/account_budget_profit_loss_report',
#             'objects': http.request.env['account_budget_profit_loss_report.account_budget_profit_loss_report'].search([]),
#         })

#     @http.route('/account_budget_profit_loss_report/account_budget_profit_loss_report/objects/<model("account_budget_profit_loss_report.account_budget_profit_loss_report"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_budget_profit_loss_report.object', {
#             'object': obj
#         })
