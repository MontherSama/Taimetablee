import pandas as pd
import plotly.express as px

class ScheduleAnalytics:
    def __init__(self, schedule):
        self.df = pd.DataFrame(schedule)
    
    def generate_summary_report(self):
        """تقرير إحصائي شامل"""
        report = {
            "total_classes": len(self.df),
            "rooms_utilization": self._calculate_room_utilization(),
            "instructor_load": self._calculate_instructor_load(),
            "conflict_analysis": self._analyze_conflicts(),
            "daily_distribution": self._daily_distribution()
        }
        return report
    
    def _calculate_room_utilization(self):
        """حساب معدل استخدام القاعات"""
        room_usage = self.df["room"].value_counts().reset_index()
        room_usage.columns = ["room", "classes"]
        fig = px.bar(room_usage, x="room", y="classes", title="استخدام القاعات")
        return fig
    
    def _calculate_instructor_load(self):
        """حساب عبء العمل على المدرسين"""
        instructor_load = self.df["instructor"].value_counts().reset_index()
        instructor_load.columns = ["instructor", "classes"]
        fig = px.pie(instructor_load, names="instructor", values="classes", title="توزيع عبء التدريس")
        return fig
    
    def _analyze_conflicts(self):
        """تحليل التعارضات (عدد المحاضرات المتداخلة لكل مورد)"""
        # يمكن تطويرها لاحقاً حسب الحاجة
        return f"عدد المحاضرات: {len(self.df)}"
    
    def _daily_distribution(self):
        """توزيع المحاضرات على الأيام"""
        day_dist = self.df["day"].value_counts().reset_index()
        day_dist.columns = ["day", "classes"]
        fig = px.bar(day_dist, x="day", y="classes", title="توزيع المحاضرات على أيام الأسبوع")
        return fig
