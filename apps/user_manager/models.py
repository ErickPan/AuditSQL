from django.db import models
from django.db.models import F
from django.contrib.auth.models import AbstractUser


# Create your models here.

class UserAccount(AbstractUser):
    """继承系统用户表"""
    uid = models.AutoField(primary_key=True, verbose_name=u'用户uid')
    avatar_file = models.ImageField(upload_to='img/%Y/%m/%d/', default=u'img/avatar1.png',
                                    verbose_name=u'用户头像')
    displayname = models.CharField(max_length=128, default='', verbose_name=u'用户显示名')
    is_active = models.BooleanField(default=False, verbose_name=u'是否激活')

    def __str__(self):
        return self.username

    def user_role(self):
        # 返回用户角色名
        return RolesDetail.objects.annotate(role_name=F('role__role_name')).get(user__uid=self.uid).role_name

    def user_group(self):
        group = GroupsDetail.objects.annotate(group_name=F('group__group_name')).filter(user__uid=self.uid).values_list(
            'group_name',
            flat=True)
        return ', '.join(group)

    class Meta:
        verbose_name = u'账户'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_useraccount'


class Roles(models.Model):
    """用户角色表"""
    role_id = models.AutoField(primary_key=True, verbose_name=u'主键')
    role_name = models.CharField(max_length=30, null=False, verbose_name=u'角色名')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    def __str__(self):
        return self.role_name

    def permission(self):
        permission_desc = PermissionDetail.objects.annotate(permission_desc=F('permission__permission_desc')).filter(
            role__role_id=self.role_id).values_list('permission_desc', flat=True)
        return ', '.join(permission_desc)

    class Meta:
        verbose_name = u'角色'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_roles'


class RolesDetail(models.Model):
    """
    用户角色详情表
    对应用户角色分组
    """
    id = models.AutoField(primary_key=True, verbose_name=u'主键')
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, null=False)
    role = models.ForeignKey(Roles, on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    class Meta:
        verbose_name = u'用户角色分组详情表'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_roles_detail'

        unique_together = ('user',)


class Permission(models.Model):
    """权限表"""
    id = models.AutoField(primary_key=True, verbose_name=u'主键')
    permission_name = models.CharField(max_length=30, null=False, verbose_name=u'权限名')
    permission_desc = models.CharField(max_length=30, default='', null=False, verbose_name=u'权限描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    def __str__(self):
        return self.permission_desc

    class Meta:
        verbose_name = u'内置权限'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_permission'


class PermissionDetail(models.Model):
    """角色对应的权限，多对多关系"""
    id = models.AutoField(primary_key=True, verbose_name=u'主键')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, null=False)
    role = models.ForeignKey(Roles, on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    class Meta:
        verbose_name = u'权限详情表'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_permission_detail'


class Groups(models.Model):
    """
    用户项目组表
    """
    group_id = models.AutoField(primary_key=True, verbose_name=u'主键')
    group_name = models.CharField(max_length=30, default='', verbose_name=u'组名')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    def __str__(self):
        return self.group_name

    class Meta:
        verbose_name = u'项目'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_groups'


class GroupsDetail(models.Model):
    """
    用户项目组详情表
    对应用户项目分组
    """
    id = models.AutoField(primary_key=True, verbose_name=u'主键')
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, null=False)
    group = models.ForeignKey(Groups, on_delete=models.CASCADE, null=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    class Meta:
        verbose_name = u'用户项目分组详情表'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_groups_detail'


class Contacts(models.Model):
    """联系人表"""
    contact_id = models.AutoField(primary_key=True, verbose_name=u'主键')
    contact_name = models.CharField(max_length=30, default='', verbose_name=u'联系人姓名')
    contact_email = models.EmailField(max_length=128, default='', verbose_name=u'联系人邮箱')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    def contact_group(self):
        group = ContactsDetail.objects.annotate(group_name=F('group__group_name')).filter(
            contact__contact_email=self.contact_email).values_list(
            'group_name', flat=True)
        return ', '.join(group)

    def __str__(self):
        return self.contact_name

    class Meta:
        verbose_name = u'联系人'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_contacts'

        unique_together = ('contact_name', 'contact_email')


class ContactsDetail(models.Model):
    """
    联系人详情表
    对应联系人分组
    """
    id = models.AutoField(primary_key=True, verbose_name=u'主键')
    contact = models.ForeignKey(Contacts, on_delete=models.CASCADE, null=False)
    group = models.ForeignKey(Groups, on_delete=models.CASCADE, null=False)
    bcc = models.IntegerField(null=False, default=0, verbose_name=u'0:不密送，1:密送')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=u'创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=u'更新时间')

    class Meta:
        verbose_name = u'联系人项目分组详情表'
        verbose_name_plural = verbose_name

        default_permissions = ()
        db_table = 'auditsql_contacts_detail'
