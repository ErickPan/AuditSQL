# -*- coding:utf-8 -*-
# edit by fuzongfei

import json
from datetime import datetime

from django.db import transaction
from django.db.models import Case, When, Value, CharField, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView

from project_manager.inception.inception_api import IncepSqlCheck
from project_manager.models import AuditContents, OlAuditContentsReply, IncepMakeExecTask, OlAuditDetail
from project_manager.ol.forms import OnlineAuditForm, OnlineReplyForm, OnlineApproveForm, OnlineAuditRecordForm, \
    OnlineFeedbackForm, OnlineCloseForm
from project_manager.utils import check_incep_alive, check_sql_filter
from user_manager.permissions import permission_required, group_permission_required, check_record_details_permission
from utils.tools import format_request


class OnlineAuditView(View):
    """线上审核内容提交"""

    def get(self, request):
        """渲染线上审核页面"""
        return render(request, 'ol_audit.html')

    @permission_required('can_commit')
    @method_decorator(check_incep_alive)
    @method_decorator(check_sql_filter)
    @transaction.atomic
    def post(self, request):
        """线上审核内容提交处理"""
        data = format_request(request)
        form = OnlineAuditForm(data)
        if form.is_valid():
            context = form.is_save(request)
            return HttpResponse(json.dumps(context))
        else:
            error = form.errors.as_text()
            context = {'status': 2, 'msg': error}
            return HttpResponse(json.dumps(context))


class OnlineRecordsView(View):
    def get(self, request):
        return render(request, 'ol_records.html')


class OnlineRecordsListView(View):
    """显示当前用户所在项目组的审核记录"""

    def get(self, request):
        data = format_request(request)
        form = OnlineAuditRecordForm(data)
        result = {}
        if form.is_valid():
            cleaned_data = form.cleaned_data
            limit_size = cleaned_data.get('limit_size')
            offset_size = cleaned_data.get('offset_size')
            search_content = cleaned_data.get('search_content')
            user_in_group = request.session['groups']
            query = AuditContents.objects.all().annotate(
                progress_value=Case(
                    When(progress='0', then=Value('待批准')),
                    When(progress='1', then=Value('未批准')),
                    When(progress='2', then=Value('已批准')),
                    When(progress='3', then=Value('处理中')),
                    When(progress='4', then=Value('已完成')),
                    When(progress='5', then=Value('已关闭')),
                    output_field=CharField(),
                ),
                progress_color=Case(
                    When(progress__in=('0',), then=Value('btn-primary')),
                    When(progress__in=('2',), then=Value('btn-warning')),
                    When(progress__in=('1', '5'), then=Value('btn-danger')),
                    When(progress__in=('3',), then=Value('btn-info')),
                    When(progress__in=('4',), then=Value('btn-success')),
                    output_field=CharField(),
                ),
                group_name=F('group__group_name'),
                group_id=F('group__group_id'),
            )
            if search_content:
                obj = query.filter(contents__icontains=search_content)
            else:
                obj = query

            ol_total = obj.filter(group_id__in=user_in_group).count()

            ol_records = obj.filter(group_id__in=user_in_group).values('group_name', 'progress_color',
                                                                       'progress_value', 'id', 'group_id', 'title',
                                                                       'proposer', 'operator', 'verifier', 'created_at'
                                                                       ).order_by('-created_at')[offset_size:limit_size]
            result = {'total': ol_total, 'rows': list(ol_records)}

        return JsonResponse(result, safe=False)


class OnlineApproveView(FormView):
    """线上工单审批操作，需要can_approve权限"""
    form_class = OnlineApproveForm

    @method_decorator(group_permission_required)
    def dispatch(self, request, *args, **kwargs):
        return super(OnlineApproveView, self).dispatch(request, *args, **kwargs)

    @permission_required('can_approve')
    @transaction.atomic
    def form_valid(self, form):
        context = form.is_save(self.request)
        return HttpResponse(json.dumps(context))

    def form_invalid(self, form):
        error = form.errors.as_text()
        context = {'status': 2, 'msg': error}
        return HttpResponse(json.dumps(context))


class OnlineFeedbackView(FormView):
    """线上工单反馈，反馈执行进度"""
    form_class = OnlineFeedbackForm

    @method_decorator(group_permission_required)
    def dispatch(self, request, *args, **kwargs):
        return super(OnlineFeedbackView, self).dispatch(request, *args, **kwargs)

    @permission_required('can_execute')
    @transaction.atomic
    def form_valid(self, form):
        context = form.is_save(self.request)
        return HttpResponse(json.dumps(context))

    def form_invalid(self, form):
        error = form.errors.as_text()
        context = {'status': 2, 'msg': error}
        return HttpResponse(json.dumps(context))


class OnlineCloseView(FormView):
    """关闭记录"""
    form_class = OnlineCloseForm

    @method_decorator(group_permission_required)
    def dispatch(self, request, *args, **kwargs):
        return super(OnlineCloseView, self).dispatch(request, *args, **kwargs)

    @permission_required('can_approve', 'can_execute')
    @transaction.atomic
    def form_valid(self, form):
        context = form.is_save(self.request)
        return HttpResponse(json.dumps(context))

    def form_invalid(self, form):
        error = form.errors.as_text()
        context = {'status': 2, 'msg': error}
        return HttpResponse(json.dumps(context))


class OnlineDetailsView(View):
    """查看线上审核记录的详情"""

    @method_decorator(check_record_details_permission)
    def get(self, request, id, group_id):
        obj = AuditContents.objects.annotate(
            progress_value=Case(
                When(progress='0', then=Value('待批准')),
                When(progress='1', then=Value('未批准')),
                When(progress='2', then=Value('已批准')),
                When(progress='3', then=Value('处理中')),
                When(progress='4', then=Value('已完成')),
                When(progress='5', then=Value('已关闭')),
                output_field=CharField(),
            ),
        )

        contents = obj.get(id=id)
        group = AuditContents.objects.filter(id=id).annotate(group_name=F('group__group_name')).values(
            'group_name').first()
        reply_contents = OlAuditContentsReply.objects.annotate(
            username=F('user__username'),
            avatar_file=F('user__avatar_file'),
        ).filter(reply__id=id).values('username', 'avatar_file', 'reply_contents', 'created_at')

        detail = OlAuditDetail.objects.get(ol=id)
        return render(request, 'ol_details.html',
                      {'contents': contents,
                       'group': group,
                       'detail': detail,
                       'reply_contents': reply_contents})


class OnlineReplyView(FormView):
    """处理用户的回复信息"""

    form_class = OnlineReplyForm

    def form_valid(self, form):
        context = form.is_save(self.request)
        return HttpResponse(json.dumps(context))

    def form_invalid(self, form):
        error = form.errors.as_text()
        context = {'status': 2, 'msg': error}
        return HttpResponse(json.dumps(context))


class OnlineGenerateTasksView(View):
    """线上工单生成执行任务"""

    @method_decorator(group_permission_required)
    @permission_required('can_execute')
    def post(self, request):
        id = request.POST.get('id')

        obj = get_object_or_404(AuditContents, pk=id)
        data = get_object_or_404(OlAuditDetail, ol=id)

        # 只要审核通过后，才能执行生成执行任务
        if obj.progress in ('2', '3', '4'):
            if IncepMakeExecTask.objects.filter(related_id=id).first():
                taskid = IncepMakeExecTask.objects.filter(related_id=id).first().taskid
                context = {'status': 0,
                           'jump_url': f'/projects/pt/perform_records/perform_details/{taskid}'}
            else:
                host = obj.host
                database = obj.database
                sql_content = data.contents

                # 实例化
                of_audit = IncepSqlCheck(sql_content, host, database, request.user.username)

                # 对OSC执行的SQL生成sqlsha1
                result = of_audit.make_sqlsha1()
                taskid = datetime.now().strftime("%Y%m%d%H%M%S%f")
                # 生成执行任务记录
                for row in result:
                    IncepMakeExecTask.objects.create(
                        uid=request.user.uid,
                        user=obj.proposer,
                        taskid=taskid,
                        dst_host=host,
                        dst_database=database,
                        sql_content=row['SQL'],
                        sqlsha1=row['sqlsha1'],
                        affected_row=row['Affected_rows'],
                        type=obj.operate_type,
                        category='1',
                        related_id=id,
                        group_id=obj.group_id
                    )

                context = {'status': 0,
                           'jump_url': f'/projects/pt/perform_records/perform_details/{taskid}'}
        else:
            context = {'status': 2, 'msg': '审核未通过或任务已关闭'}

        return HttpResponse(json.dumps(context))
