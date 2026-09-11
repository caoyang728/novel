"""
characters 测试公共辅助函数
"""
from django.contrib.auth.models import User

from apps.project.models import ProjectList as Project
from apps.characters.models import Character


def _create_test_data():
    """创建测试所需的 user、project、character"""
    user = User.objects.create_user(username='testuser', password='testpass123')
    project = Project.objects.create(
        user=user,
        title='测试项目',
        genre='xuanhuan',
        description='测试用项目'
    )
    character = Character.objects.create(
        project=project,
        name='张三',
        role_type='主角',
        gender='男',
        age=25,
        faction='正派',
        identity='剑仙',
        tagline='一剑破万法',
        content='# 性格\n\n勇敢果断',
        source='manual',
    )
    return user, project, character
