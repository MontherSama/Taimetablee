import logging
from collections import defaultdict
from typing import List, Dict
from model import Schedule, TimeSlot, Config, Instructor
from datetime import time

logger = logging.getLogger(__name__)

class SoftConstraintsValidator:
    """محقق القيود المرنة مع دعم الأوزان المخصصة"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def penalty(self, schedules: List[Schedule]) -> Dict[str, float]:
        """حساب العقوبات المرجحة لجميع القيود المرنة"""
        penalties = defaultdict(float)
        
        # القيود الأساسية
        penalties["room_conflict"] = self.room_conflict_penalty(schedules)
        penalties["instructor_conflict"] = self.instructor_conflict_penalty(schedules)
        penalties["group_conflict"] = self.group_conflict_penalty(schedules)
        
        # القيود المرنة
        penalties["facility_mismatch"] = self.facility_mismatch_penalty(schedules)
        penalties["time_preference"] = self.time_preference_penalty(schedules)
        penalties["minimize_gaps"] = self.minimize_gaps_penalty(schedules)
        penalties["balance_room_usage"] = self.balance_room_usage_penalty(schedules)
        penalties["instructor_preference"] = self.instructor_preference_penalty(schedules)
        penalties["merge_bonus"] = -self.merge_bonus(schedules)  # مكافأة
        
        return penalties

    def room_conflict_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة تعارض استخدام القاعة"""
        room_sessions = defaultdict(list)
        for s in schedules:
            room_sessions[s.room_id].append(s)
        
        penalty = 0
        for room_id, sessions in room_sessions.items():
            sessions.sort(key=lambda s: s.time_slot.start_minutes)
            for i in range(1, len(sessions)):
                if sessions[i-1].time_slot.overlaps(sessions[i].time_slot):
                    penalty += 1
        return penalty * 100  # وزن ثقيل

    def instructor_conflict_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة تعارض المدرسين"""
        instructor_sessions = defaultdict(list)
        for s in schedules:
            instructor_sessions[s.instructor_id].append(s)
        
        penalty = 0
        for instructor_id, sessions in instructor_sessions.items():
            sessions.sort(key=lambda s: s.time_slot.start_minutes)
            for i in range(1, len(sessions)):
                if sessions[i-1].time_slot.overlaps(sessions[i].time_slot):
                    penalty += 1
        return penalty * 200  # وزن ثقيل

    def group_conflict_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة تعارض المجموعات (عدا الفروع)"""
        group_sessions = defaultdict(list)
        for s in schedules:
            group_sessions[s.group_id].append(s)
        
        penalty = 0
        for group_id, sessions in group_sessions.items():
            sessions.sort(key=lambda s: s.time_slot.start_minutes)
            for i in range(1, len(sessions)):
                if sessions[i-1].time_slot.overlaps(sessions[i].time_slot):
                    # السماح للفروع فقط بالتداخل
                    if "_sub" not in sessions[i-1].course_id or "_sub" not in sessions[i].course_id:
                        penalty += 1
        return penalty * 150  # وزن ثقيل

    def facility_mismatch_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة عدم توافق مرافق القاعة مع متطلبات المادة"""
        penalty = 0
        for s in schedules:
            if s.assigned_course.required_facilities:
                for facility in s.assigned_course.required_facilities:
                    if facility not in s.assigned_room.facilities:
                        penalty += 1
        return penalty

    def time_preference_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة الجدولة في أوقات غير مفضلة"""
        penalty = 0
        unfavorable_start = time(8, 0)  # أول الصباح
        unfavorable_end = time(16, 0)   # نهاية اليوم
        
        for s in schedules:
            start = s.time_slot.start_time
            if start <= unfavorable_start or start >= unfavorable_end:
                penalty += 1
        return penalty

    def minimize_gaps_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة وجود فجوات كبيرة بين محاضرات المجموعة"""
        group_sessions = defaultdict(list)
        for s in schedules:
            group_sessions[s.group_id].append(s)
        
        penalty = 0
        for group_id, sessions in group_sessions.items():
            sessions.sort(key=lambda s: s.time_slot.start_minutes)
            for i in range(1, len(sessions)):
                if sessions[i-1].time_slot.day == sessions[i].time_slot.day:
                    gap = sessions[i].time_slot.start_minutes - sessions[i-1].time_slot.end_minutes
                    if gap > 60:  # أكثر من ساعة
                        penalty += (gap - 60) / 30  # 0.5 لكل 30 دقيقة إضافية
        return penalty

    def balance_room_usage_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة عدم توازن استخدام القاعات"""
        room_usage = defaultdict(int)
        for s in schedules:
            room_usage[s.room_id] += s.time_slot.duration
        
        if not room_usage:
            return 0
        
        avg_usage = sum(room_usage.values()) / len(room_usage)
        imbalance = sum(abs(usage - avg_usage) for usage in room_usage.values())
        return imbalance / 100  # تطبيع القيمة

    def instructor_preference_penalty(self, schedules: List[Schedule]) -> float:
        """عقوبة مخالفة تفضيلات المدرسين"""
        penalty = 0
        for s in schedules:
            instructor = s.assigned_instructor
            if instructor.preferred_days and s.time_slot.day not in instructor.preferred_days:
                penalty += 1
            if instructor.preferred_slots:
                slot_matched = any(
                    slot.day == s.time_slot.day and
                    slot.start_time <= s.time_slot.start_time <= slot.end_time
                    for slot in instructor.preferred_slots
                )
                if not slot_matched:
                    penalty += 1
        return penalty

    def merge_bonus(self, schedules: List[Schedule]) -> float:
        """مكافأة دمج المجموعات في قاعات كبيرة"""
        merged_courses = defaultdict(list)
        bonus = 0
        
        for s in schedules:
            if s.assigned_course.can_merge:
                key = (s.assigned_course.id, s.time_slot)
                merged_courses[key].append(s)
        
        for (course_id, slot), sessions in merged_courses.items():
            if len(sessions) > 1:
                bonus += len(sessions)
                # مكافأة إضافية لدمج تخصصات مختلفة
                groups = {s.assigned_group.major for s in sessions}
                if len(groups) > 1:
                    bonus += 2
        return bonus