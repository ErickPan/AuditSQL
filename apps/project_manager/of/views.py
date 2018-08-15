# -*- coding:utf-8 -*-
# edit by fuzongfei
import json

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from project_manager.of.forms import OfflineAuditForm, HookWorkOrderForm
from project_manager.utils import check_incep_alive, check_sql_filter
from user_manager.permissions import permission_required, order_permission_required
from utils.tools import format_request


class OfflineWorkOrderAuditView(View):
    """线下工单生成执行任务"""

    def get(self, request):
        return render(request, 'of_work_order_audit.html')

    @method_decorator(check_incep_alive)
    @method_decorator(check_sql_filter)
    @permission_required('can_commit')
    @transaction.atomic
    def post(self, request):
        data = format_request(request)
        form = OfflineAuditForm(data)
        if form.is_valid():
            context = form.save(request)
            return HttpResponse(json.dumps(context))
        else:
            error = form.errors.as_text()
            context = {'status': 2, 'msg': error}

            return HttpResponse(json.dumps(context))


class MOneWorkOrderAuditView(View):
    def get(self, request):
        return render(request, 'test_work_order_audit.html')


class HookWorkOrderView(View):
    """工单扭转, 处理钩子数据"""

    @order_permission_required('can_execute')
    def post(self, request):
        data = format_request(request)
        form = HookWorkOrderForm(data)
        if form.is_valid():
            context = form.save(request)
            return HttpResponse(json.dumps(context))
        else:
            error = form.errors.as_text()
            context = {'status': 2, 'msg': error}

            return HttpResponse(json.dumps(context))
