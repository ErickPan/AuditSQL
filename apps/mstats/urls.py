# -*- coding:utf-8 -*-
# edit by fuzongfei

from django.contrib.auth.decorators import login_required
from django.urls import path, re_path

from mstats.views import RenderMySQLUserView, MySQLUserView, MysqlUserManager, RBackupTaskView, BackupTaskView, \
    BackupTaskDetailView, BackupTaskPreviewView, BackupTaskPreviewListView, GetBackupDiskUsedView, \
    RSchemaMonitorTaskView, SchemaMonitorTaskView, MySQLQueryView, RMySQLQueryView

urlpatterns = [
    path(r'r_mysql_user_manager/', login_required(RenderMySQLUserView.as_view()), name='p_r_mysql_user_manager'),
    path(r'mysql_user/', login_required(MySQLUserView.as_view()), name='p_mysql_user'),
    path(r'mysql_user_manager/', login_required(MysqlUserManager.as_view()), name='p_mysql_user_manager'),
    # 监控表结构定时任务
    path(r'rperiodic_task/', login_required(RSchemaMonitorTaskView.as_view()), name='p_rschema_monitor_task'),
    path(r'periodic_task/', login_required(SchemaMonitorTaskView.as_view()), name='p_schema_monitor_task'),
    # 监控备份定时任务
    path(r'rbackup_task/', login_required(RBackupTaskView.as_view()), name='p_rbackup_task'),
    path(r'backup_task/', login_required(BackupTaskView.as_view()), name='p_backup_task'),
    # 获取备份任务信息
    path(r'backup_task_detail/', login_required(BackupTaskDetailView.as_view()), name='p_backup_task_detail'),
    re_path(r'backup_task_preview/(?P<id>\d+)/', login_required(BackupTaskPreviewView.as_view())),
    re_path(r'backup_task_preview_list', login_required(BackupTaskPreviewListView.as_view()),
            name='p_backup_task_preview_list'),
    re_path(r'get_backup_disk_used', login_required(GetBackupDiskUsedView.as_view()),
            name='p_get_backup_disk_used'),
    path(r'rquery/', login_required(RMySQLQueryView.as_view()), name='p_rquery'),
    path(r'query/', login_required(MySQLQueryView.as_view()), name='p_query')
]
