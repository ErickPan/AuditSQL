# -*- coding:utf-8 -*-
# edit by fuzongfei

import json
from ast import literal_eval

from channels.layers import get_channel_layer
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from apps.project_manager.inception.inception_api import GetBackupApi, IncepSqlCheck
from project_manager.models import IncepMakeExecTask
from project_manager.tasks import incep_async_tasks, \
    stop_incep_osc, get_osc_percent
from project_manager.utils import check_incep_alive
from user_manager.permissions import perform_tasks_permission_required
from utils.tools import format_request

channel_layer = get_channel_layer()


class PerformRecordsView(View):
    """渲染执行任务列表页"""

    def get(self, request):
        return render(request, 'perform_records.html')


class PerformRecordsListView(View):
    """渲染执行任务列表页表格数据"""

    def get(self, request):
        exec_tasks = []
        user_in_group = '(' + str(request.session['groups'][0]) + ')' if len(request.session['groups']) == 1 else tuple(
            request.session['groups'])
        query = f"select a.id,a.user,a.taskid,a.dst_host,a.dst_database,a.make_time, b.group_name," \
                f"case a.category when '0' then '线下任务' when '1' then '线上任务' end as category " \
                f"from auditsql_incep_tasks as a join auditsql_groups as b " \
                f"on a.group_id = b.group_id where b.group_id in {user_in_group} group by a.taskid " \
                f"order by a.make_time  desc"
        for row in IncepMakeExecTask.objects.raw(query):
            exec_tasks.append({'user': row.user,
                               'taskid': row.taskid,
                               'group_name': row.group_name,
                               'category': row.category,
                               'dst_host': row.dst_host,
                               'dst_database': row.dst_database,
                               'make_time': row.make_time})
        return JsonResponse(list(exec_tasks), safe=False)


class PerformResultsView(View):
    """返回执行任务执行结果和备份信息"""

    def get(self, request):
        id = request.GET.get('id')
        if IncepMakeExecTask.objects.get(id=id).exec_status in ('1', '4'):
            sql_detail = IncepMakeExecTask.objects.get(id=id)
            sequence_result = {'backupdbName': sql_detail.backup_dbname, 'sequence': sql_detail.sequence}
            rollback_sql = GetBackupApi(sequence_result).get_rollback_statement()

            exec_log = sql_detail.exec_log if sql_detail.exec_log else ''

            # 此处要将exec_log去字符串处理，否则无法转换为json
            data = {'rollback_log': rollback_sql, 'exec_log': literal_eval(exec_log)}
            context = {'status': 0, 'msg': '', 'data': data}
        else:
            context = {'status': 2, 'msg': '该SQL未被执行，无法查询状态信息'}

        return HttpResponse(json.dumps(context))


class PerformDetailsView(View):
    """渲染指定执行任务详情页面"""

    def get(self, request, taskid):
        return render(request, 'perform_details.html', {'taskid': taskid})


class PerformDetailsListView(View):
    """渲染指定执行任务页面数据"""

    def get(self, request):
        taskid = request.GET.get('taskid')

        query = f"select id,user,sqlsha1,sql_content,taskid,case exec_status " \
                f"when '0' then '未执行' when '1' then '已完成' when '2' then '处理中' when '3' then '回滚中' " \
                f"when '4' then '已回滚' end as exec_status," \
                f"case category when '0' then '线下任务' when '1' then '线上任务' end as category" \
                f" from auditsql_incep_tasks where taskid={taskid}".format(taskid=taskid)
        i = 0
        task_details = []
        for row in IncepMakeExecTask.objects.raw(query):
            task_details.append({
                'sid': i,
                'id': row.id,
                'user': row.user,
                'category': row.category,
                'sqlsha1': row.sqlsha1,
                'sql_content': row.sql_content,
                'taskid': row.taskid,
                'exec_status': row.exec_status
            })
            i += 1
        del task_details[0]
        return HttpResponse(json.dumps(task_details))


class PerformExecView(View):
    """执行任务-开始执行"""

    @method_decorator(check_incep_alive)
    @perform_tasks_permission_required('can_execute')
    @transaction.atomic
    def post(self, request):
        data = format_request(request)
        id = data.get('id')
        obj = IncepMakeExecTask.objects.get(id=id)
        host = obj.dst_host
        database = obj.dst_database
        sql = obj.sql_content + ';'

        status = ''
        query = f"select id,group_concat(exec_status) as exec_status from auditsql_incep_tasks " \
                f"where taskid={obj.taskid} group by taskid"
        for row in IncepMakeExecTask.objects.raw(query):
            status = row.exec_status.split(',')

        # 每次只能执行一条任务，不可同时执行，避免数据库压力
        if '2' in status or '3' in status:
            context = {'status': 2, 'msg': '请等待当前任务执行完成'}
        else:
            # 避免任务重复点击执行
            if obj.exec_status != '0':
                context = {'status': 2, 'msg': '请不要重复操作任务'}
            else:
                # 将任务进度设置为：处理中
                obj.exec_status = 2
                obj.save()

                # 如果sqlsha1存在，使用pt-online-schema-change执行
                if obj.sqlsha1:
                    # 异步执行SQL任务
                    r = incep_async_tasks.delay(user=request.user.username,
                                                id=id,
                                                sql=sql,
                                                host=host,
                                                database=database,
                                                sqlsha1=obj.sqlsha1,
                                                backup='yes',
                                                exec_status=1)
                    task_id = r.task_id
                    # 将celery task_id写入到表
                    obj.celery_task_id = task_id
                    obj.save()
                    # 获取OSC执行进度
                    get_osc_percent.delay(task_id=task_id)

                    context = {'status': 0, 'msg': '提交处理，请查看输出'}

                else:
                    # 当affected_row>2000时，只执行不备份
                    if obj.affected_row > 2000:
                        incep_async_tasks.delay(user=request.user.username,
                                                id=id,
                                                sql=sql,
                                                host=host,
                                                database=database,
                                                exec_status=1)
                    else:
                        # 当affected_row<=2000时，执行并备份
                        incep_async_tasks.delay(user=request.user.username,
                                                id=id,
                                                backup='yes',
                                                sql=sql,
                                                host=host,
                                                database=database,
                                                exec_status=1)

                    context = {'status': 0, 'msg': '提交处理，请查看输出'}
        return HttpResponse(json.dumps(context))


class PerformStopView(View):
    """
    执行任务-停止OSC执行
    只支持停止修改表结构的操作
    """

    @method_decorator(check_incep_alive)
    @perform_tasks_permission_required('can_execute')
    @transaction.atomic
    def post(self, request):
        id = request.POST.get('id')
        obj = IncepMakeExecTask.objects.get(id=id)
        celery_task_id = obj.celery_task_id

        if obj.exec_status in ('0', '1', '4'):
            context = {'status': 2, 'msg': '请不要重复操作任务'}
        else:
            # 关闭正在执行的任务
            stop_incep_osc.delay(user=request.user.username,
                                 id=id,
                                 celery_task_id=celery_task_id)
            context = {'status': 0, 'msg': '提交处理，请查看输出'}
        return HttpResponse(json.dumps(context))


class PerformRollbackView(View):
    """
    执行任务-回滚操作
    回滚操作不会进行再次进行备份
    """

    @method_decorator(check_incep_alive)
    @perform_tasks_permission_required('can_execute')
    @transaction.atomic
    def post(self, request):
        data = format_request(request)
        id = data.get('id')
        obj = IncepMakeExecTask.objects.get(id=id)
        host = obj.dst_host
        database = obj.dst_database

        if obj.exec_status in ('0', '3', '4'):
            context = {'status': 2, 'msg': '请不要重复操作'}
        else:
            # 获取回滚语句
            rollback_sql = GetBackupApi(
                {'backupdbName': obj.backup_dbname, 'sequence': obj.sequence}).get_rollback_statement()
            if rollback_sql is None:
                context = {'status': 2, 'msg': '没有找到备份记录，回滚失败'}
            else:
                of_audit = IncepSqlCheck(rollback_sql, obj.dst_host, obj.dst_database, request.user.username)
                result = of_audit.make_sqlsha1()[1]

                rollback_sql = result['SQL'] + ';'
                rollback_sqlsha1 = result['sqlsha1']

                # 将任务进度设置为：回滚中
                obj.exec_status = 3
                obj.rollback_sqlsha1 = rollback_sqlsha1
                obj.save()

                if result['sqlsha1']:
                    # 异步执行SQL任务
                    r = incep_async_tasks.delay(user=request.user.username,
                                                id=id,
                                                host=host,
                                                database=database,
                                                sql=rollback_sql,
                                                sqlsha1=rollback_sqlsha1,
                                                exec_status=4)
                    task_id = r.task_id
                    # 将celery task_id写入到表
                    obj.celery_task_id = task_id
                    obj.save()
                    # 获取OSC执行进度
                    get_osc_percent.delay(task_id=task_id)

                    context = {'status': 0, 'msg': '提交处理，请查看输出'}
                else:
                    incep_async_tasks.delay(user=request.user.username,
                                            id=id,
                                            sql=rollback_sql,
                                            host=host,
                                            database=database,
                                            exec_status=4)

                    context = {'status': 0, 'msg': '提交处理，请查看输出'}
        return HttpResponse(json.dumps(context))
