from django.db import models
from apps.project.models import ProjectList


class TimelineEvent(models.Model):
    """时间线事件"""
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='timeline_events', verbose_name='所属项目')
    title = models.CharField(max_length=255, verbose_name='事件标题')
    description = models.TextField(blank=True, verbose_name='事件描述')
    era_unit = models.CharField(max_length=50, default='', blank=True, verbose_name='纪元单位')
    start_year = models.IntegerField(default=0, verbose_name='开始年')
    start_month = models.IntegerField(default=0, verbose_name='开始月')
    end_year = models.IntegerField(default=0, verbose_name='结束年')
    end_month = models.IntegerField(default=0, verbose_name='结束月')
    is_active = models.BooleanField(default=True, verbose_name='是否使用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'timeline_event'
        verbose_name = '时间线事件'
        verbose_name_plural = '时间线事件'
        ordering = ['start_year', 'start_month', 'end_year', 'end_month']

    def __str__(self):
        time_str = self.format_time_range()
        return f'{self.title} ({time_str})' if time_str else self.title

    def format_time_range(self):
        """格式化时间范围显示"""
        start = self.format_time_point(self.start_year, self.start_month)
        end = self.format_time_point(self.end_year, self.end_month)
        if start and end:
            return f'{start} - {end}'
        return start or end or ''

    def format_time_point(self, year, month):
        """格式化单个时间点，0年显示为元年"""
        if year == 0 and month == 0:
            return ''
        era = self.era_unit or ''
        parts = []
        if era:
            parts.append(era)
        if year == 0:
            parts.append('元年')
        elif year < 0 and era:
            parts.append(f'前{abs(year)}年')
        else:
            parts.append(f'{year}年')
        if month != 0:
            parts.append(f'{month}月')
        return ''.join(parts)

    def format_time_range_for_llm(self):
        """格式化时间范围给LLM使用，使用纯数字避免'元年'歧义"""
        era = self.era_unit or ''
        parts = []
        if era:
            parts.append(f'纪元={era}')
        parts.append(f'起始年={self.start_year}')
        if self.start_month != 0:
            parts.append(f'起始月={self.start_month}')
        parts.append(f'结束年={self.end_year}')
        if self.end_month != 0:
            parts.append(f'结束月={self.end_month}')
        return ', '.join(parts)
