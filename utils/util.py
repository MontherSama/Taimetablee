import json
import logging
import os
from copy import deepcopy
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
import plotly.graph_objects as go
import plotly.express as px

from typing import List, Dict, Any
from model import Room, Schedule, Instructor, Group, Course, Config as ModelConfig
from algorithm.cp_algorithm import CPSatScheduler
from algorithm.soft_constraints_handler import SoftConstraintsOptimizer
from algorithm.genetic_optimizer import EnhancedGeneticOptimizer, perturb

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def load_sample_data():
    """إرجاع بيانات تجريبية جاهزة للاختبار"""
    return {
        "rooms": [
            {"id": "R101", "name": "قاعة 101", "type": "نظرية", "capacity": 40, "facilities": ["بروجكتر", "سبورة ذكية"]},
            {"id": "R102", "name": "قاعة 102", "type": "نظرية", "capacity": 50, "facilities": ["بروجكتر", "إنترنت"]},
            {"id": "L201", "name": "مختبر 201", "type": "عملي", "capacity": 30, "facilities": ["حواسيب", "شبكة"]}
        ],
        "instructors": [
            {"id": "I001", "name": "د. أحمد محمد", "expertise": ["الحاسوب", "البرمجة"], "max_teaching_hours": 18},
            {"id": "I002", "name": "د. فاطمة علي", "expertise": ["الرياضيات", "الإحصاء"], "max_teaching_hours": 20},
            {"id": "I003", "name": "د. خالد محمود", "expertise": ["الشبكات", "الأمن"], "max_teaching_hours": 16}
        ],
        "groups": [
            {"id": "G1", "major": "علوم الحاسوب", "level": 3, "student_count": 35},
            {"id": "G2", "major": "هندسة البرمجيات", "level": 3, "student_count": 30},
            {"id": "G3", "major": "أمن المعلومات", "level": 4, "student_count": 25}
        ],
        "courses": [
            {"id": "CS101", "name": "برمجة الحاسوب", "duration": 90, "course_type": "نظرية", "instructor_id": "I001", "group_id": "G1"},
            {"id": "MATH201", "name": "الرياضيات المتقدمة", "duration": 90, "course_type": "نظرية", "instructor_id": "I002", "group_id": "G1"},
            {"id": "NET301", "name": "شبكات الحاسوب", "duration": 120, "course_type": "عملي", "instructor_id": "I003", "group_id": "G3"}
        ]
    }

def load_data_from_file(uploaded_file):
    """تحميل البيانات من ملف JSON"""
    try:
        return json.load(uploaded_file)
    except Exception as e:
        logger.error(f"خطأ في تحميل الملف: {str(e)}")
        return None

def save_config(config, filename="config.json"):
    """حفظ الإعدادات في ملف"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(config.__dict__, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الإعدادات: {str(e)}")
        return False


def schedule_to_dataframe(schedules: List[Schedule]) -> pd.DataFrame:
    # تسطيح القائمة إذا كانت تحتوي على قوائم فرعية
    if schedules and isinstance(schedules[0], list):
        schedules = [item for sublist in schedules for item in sublist]
    # فلترة العناصر غير الصحيحة
    schedules = [s for s in schedules if hasattr(s, "time_slot") and hasattr(s, "assigned_course")]
    data = []
    for s in schedules:
        # حوّل start_time و end_time إلى نصّ واضح
        start_str = s.time_slot.start_time.strftime("%H:%M") if s.time_slot.start_time else ""
        end_str   = s.time_slot.end_time.strftime("%H:%M") if s.time_slot.end_time else ""
        day_int   = s.time_slot.day.value if hasattr(s.time_slot.day, "value") else int(s.time_slot.day)
        slot_data = s.time_slot.to_serializable()
        if not slot_data:
            logger.warning(f"⚠️ الفترة الزمنية غير صالحة للمادة {s.assigned_course.name} في المجموعة {s.group_id}")
            continue
        data.append({
            "course_id": s.course_id,
            "course_name": s.assigned_course.name,
            "group_id": s.group_id,
            "room_id": s.room_id,
            "room_name": s.assigned_room.name,
            "instructor_id": s.instructor_id,
            "instructor_name": s.assigned_instructor.name,
            "day": slot_data['day'],
            "day_name": s.time_slot.day.to_arabic(),
            "start_time": f"{slot_data['start_time']}:00" if ':' in slot_data['start_time'] and len(slot_data['start_time']) == 5 else slot_data['start_time'],
            "end_time": f"{slot_data['end_time']}:00" if ':' in slot_data['end_time'] and len(slot_data['end_time']) == 5 else slot_data['end_time'],
            "duration_minutes": slot_data['duration'],
            "penalty_score": float(s.penalty_score)
        })
    return pd.DataFrame(data)

    
def analyze_conflicts(schedules: List[Schedule]) -> Dict[str, Any]:
    """
    تحليل التعارضات في الجدول وتصنيفها حسب القاعات، المحاضرين، والمجموعات.
    :param schedules: قائمة الجدول
    :return: dict يحتوي تفاصيل التعارضات
    """
    conflicts = {
        "room": defaultdict(list),
        "instructor": defaultdict(list),
        "group": defaultdict(list)
    }
    room_slots = defaultdict(list)
    instructor_slots = defaultdict(list)
    group_slots = defaultdict(list)
    for s in schedules:
        room_slots[s.room_id].append(s.time_slot)
        instructor_slots[s.instructor_id].append(s.time_slot)
        group_slots[s.group_id].append(s.time_slot)
    for room_id, slots in room_slots.items():
        sorted_slots = sorted(slots, key=lambda ts: ((ts.day.value if hasattr(ts.day, "value") else int(ts.day)), ts.start_minutes))
        for i in range(1, len(sorted_slots)):
            if sorted_slots[i-1].overlaps(sorted_slots[i]):
                conflicts["room"][room_id].append((sorted_slots[i-1], sorted_slots[i]))
    for instructor_id, slots in instructor_slots.items():
        sorted_slots = sorted(slots, key=lambda ts: ((ts.day.value if hasattr(ts.day, "value") else int(ts.day)), ts.start_minutes))
        for i in range(1, len(sorted_slots)):
            if sorted_slots[i-1].overlaps(sorted_slots[i]):
                conflicts["instructor"][instructor_id].append((sorted_slots[i-1], sorted_slots[i]))
    for group_id, slots in group_slots.items():
        sorted_slots = sorted(slots, key=lambda ts: ((ts.day.value if hasattr(ts.day, "value") else int(ts.day)), ts.start_minutes))
        for i in range(1, len(sorted_slots)):
            if sorted_slots[i-1].overlaps(sorted_slots[i]):
                conflicts["group"][group_id].append((sorted_slots[i-1], sorted_slots[i]))
    total_conflicts = (
        sum(len(v) for v in conflicts["room"].values()) +
        sum(len(v) for v in conflicts["instructor"].values()) +
        sum(len(v) for v in conflicts["group"].values())
    )
    logger.info(f"⚠️ تم اكتشاف {total_conflicts} تعارض في الجدول")
    return conflicts



def visualize_conflicts(conflicts):
    """إنشاء مخططات لتحليل التعارضات مع تحسينات"""
    all_data = []
    if conflicts.get("room"):
        for room, conflicts_list in conflicts["room"].items():
            all_data.append({
                "الموارد": room,
                "عدد التعارضات": len(conflicts_list),
                "النوع": "قاعة"
            })
    if conflicts.get("instructor"):
        for inst, conflicts_list in conflicts["instructor"].items():
            all_data.append({
                "الموارد": inst,
                "عدد التعارضات": len(conflicts_list),
                "النوع": "محاضر"
            })
    if conflicts.get("group"):
        for group, conflicts_list in conflicts["group"].items():
            all_data.append({
                "الموارد": group,
                "عدد التعارضات": len(conflicts_list),
                "النوع": "مجموعة"
            })
    if not all_data:
        return go.Figure()
    df = pd.DataFrame(all_data)
    fig = px.bar(
        df, 
        x="الموارد", 
        y="عدد التعارضات",
        color="النوع",
        barmode="group",
        title="تحليل التعارضات في الجدول",
        height=500,
        text="عدد التعارضات",
        color_discrete_map={
            "قاعة": "#FF5252",
            "محاضر": "#4FC3F7",
            "مجموعة": "#66BB6A"
        }
    )
    fig.update_layout(
        template="plotly_white",
        legend_title="نوع التعارض",
        xaxis_title="الموارد",
        yaxis_title="عدد التعارضات",
        hovermode="x unified"
    )
    fig.update_traces(textposition="outside")
    return fig


# دالة لإنشاء مخطط جانت
def create_gantt_chart(schedule_df, group_id):
    # تأكد من وجود الأعمدة المطلوبة
    if 'parent_group' not in schedule_df.columns:
        schedule_df = schedule_df.copy()
        schedule_df['parent_group'] = schedule_df['group_id'].apply(lambda gid: gid.split('_sub')[0] if '_sub' in gid else gid)
    if 'subgroup_info' not in schedule_df.columns:
        schedule_df['subgroup_info'] = schedule_df['group_id'].apply(lambda gid: f"ابن {gid.split('_sub')[1]}" if '_sub' in gid else '-')

    # دعم عرض جميع الأبناء مع الأب في نفس المخطط
    if group_id in schedule_df['parent_group'].values:
        group_df = schedule_df[schedule_df['parent_group'] == group_id].copy()
    else:
        group_df = schedule_df[schedule_df['group_id'] == group_id].copy()
    if group_df.empty:
        return None, "لا توجد محاضرات للمجموعة المحددة"
    
    # تحويل الأيام إلى أرقام متسلسلة للرسم
    day_order = {
        "السبت": 0,
        "الأحد": 1,
        "الاثنين": 2,
        "الثلاثاء": 3,
        "الأربعاء": 4,
        "الخميس": 5,
        "الجمعة": 6
    }
    
    group_df['day_order'] = group_df['day_name'].map(day_order)
    
    # تحويل أوقات البدء والنهاية إلى دقائق
    group_df['start_min'] = group_df['start_time'].apply(time_to_minutes)
    group_df['end_min'] = group_df['end_time'].apply(time_to_minutes)
    group_df['duration_min'] = group_df['end_min'] - group_df['start_min']
    
    # إنشاء الشكل
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # الألوان لكل محاضرة
    unique_courses = group_df['course_name'].unique()
    if len(unique_courses) > 0:
        color_map = plt.colormaps['tab20'](range(len(unique_courses)))
    else:
        color_map = ['blue']  # لون افتراضي إذا لم يكن هناك مقررات
    
    # رسم كل محاضرة
    for i, row in group_df.iterrows():
        y_pos = row['day_order'] * 10  # وضع كل يوم في صف منفصل
        
        # تحديد لون المحاضرة
        if row['course_name'] in unique_courses:
            color_idx = list(unique_courses).index(row['course_name'])
            color = color_map[color_idx]
        else:
            color = 'blue'
        
        # رسم المستطيل
        ax.broken_barh([(row['start_min'], row['duration_min'])], 
                      (y_pos, 8), 
                      facecolors=color,
                      edgecolor='black',
                      linewidth=1)
        
        # إضافة نص داخل المستطيل
        text_x = row['start_min'] + row['duration_min'] / 2
        text_y = y_pos + 4
        
        # معلومات المحاضرة مع توضيح الابن إن وجد
        if row['subgroup_info'] != "-":
            info = f"[{row['subgroup_info']}]\n{row['course_name']}\n{row['instructor_name']}\n{row['room_name']}"
        else:
            info = f"{row['course_name']}\n{row['instructor_name']}\n{row['room_name']}"
        ax.text(text_x, text_y, info, 
               ha='center', va='center', 
               fontsize=9, color='white',
               bbox=dict(facecolor='black', alpha=0.5, boxstyle='round,pad=0.2'))
    
    # إعداد المحور الرأسي (الأيام)
    ax.set_yticks([d * 10 + 4 for d in day_order.values()])
    ax.set_yticklabels(day_order.keys())
    
    # إعداد المحور الأفقي (الوقت)
    start_min = group_df['start_min'].min()
    end_min = group_df['end_min'].max()
    
    # إنشاء تسميات الوقت كل ساعة
    hours = range(0, 24)
    hour_labels = [f"{h:02d}:00" for h in hours]
    hour_positions = [h * 60 for h in hours if h * 60 >= start_min and h * 60 <= end_min]
    
    ax.set_xticks(hour_positions)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours if h * 60 >= start_min and h * 60 <= end_min])
    
    # إضافة خطوط الشبكة
    ax.grid(True, axis='x', linestyle='--', alpha=0.7)
    
    # إضافة عناوين
    ax.set_title(f'جدول المحاضرات للمجموعة: {group_id}', fontsize=16)
    ax.set_xlabel('الوقت', fontsize=12)
    ax.set_ylabel('اليوم', fontsize=12)
    
    # إضافة وسيلة إيضاح
    if len(unique_courses) > 0:
        handles = []
        for i, course in enumerate(unique_courses):
            handles.append(plt.Rectangle((0,0), 1, 1, color=color_map[i]))
        
        ax.legend(handles, unique_courses, 
                 title='المقررات الدراسية', 
                 loc='upper left', bbox_to_anchor=(1, 1))
    
    plt.tight_layout()
    return fig, None


# def load_config(filename="config.json"):
#     """تحميل الإعدادات من ملف"""
#     if os.path.exists(filename):
#         try:
#             with open(filename, "r", encoding="utf-8") as f:
#                 data = json.load(f)
#             return Config(**data)
#         except Exception as e:
#             logger.error(f"خطأ في تحميل الإعدادات: {str(e)}")
#             return Config()
#     else:
#         return Config()
    
    
# دالة مساعدة لتحويل وقت النص إلى دقائق
def time_to_minutes(time_str):
    """تحويل تنسيق الوقت HH:MM أو HH:MM:SS إلى دقائق منذ بداية اليوم"""
    parts = time_str.split(':')
    if len(parts) == 2:
        hours, minutes = map(int, parts)
        seconds = 0
    elif len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
    else:
        raise ValueError(f"تنسيق وقت غير مدعوم: {time_str}")
    return hours * 60 + minutes + (seconds // 60)

def analyze_dict_conflicts(schedules: List[Dict]) -> Dict[str, Any]:
    """
    تحليل التعارضات في الجدول وتصنيفها حسب القاعات، المحاضرين، والمجموعات.
    :param schedules: قائمة الجدول كقواميس
    :return: dict يحتوي تفاصيل التعارضات
    """
    conflicts = {
        "room": defaultdict(list),
        "instructor": defaultdict(list),
        "group": defaultdict(list)
    }
    
    # تحويل الأيام إلى أرقام
    day_order = {
        "السبت": 0,
        "الأحد": 1,
        "الاثنين": 2,
        "الثلاثاء": 3,
        "الأربعاء": 4,
        "الخميس": 5,
        "الجمعة": 6
    }
    
    # دالة لتحويل الوقت إلى دقائق
    def time_to_minutes(time_str):
        parts = time_str.split(':')
        if len(parts) >= 2:
            hours = int(parts[0])
            minutes = int(parts[1])
            return hours * 60 + minutes
        return 0

    # تجميع الجلسات حسب القاعة
    room_sessions = defaultdict(list)
    for s in schedules:
        room_sessions[s['room']].append(s)
    
    for room, sessions in room_sessions.items():
        # تجميع الجلسات حسب اليوم
        by_day = defaultdict(list)
        for s in sessions:
            by_day[s['day']].append(s)
        
        for day, day_sessions in by_day.items():
            # تحويل الجلسات إلى دقائق وترتيبها
            sessions_with_minutes = []
            for s in day_sessions:
                start_minutes = time_to_minutes(s['start'])
                end_minutes = time_to_minutes(s['end'])
                sessions_with_minutes.append((start_minutes, end_minutes, s))
            
            sessions_with_minutes.sort(key=lambda x: x[0])
            for i in range(1, len(sessions_with_minutes)):
                prev_start, prev_end, prev_s = sessions_with_minutes[i-1]
                curr_start, curr_end, curr_s = sessions_with_minutes[i]
                if prev_end > curr_start:
                    # يوجد تعارض
                    conflicts["room"][room].append((prev_s, curr_s))
    
    # نفس المنطق للمحاضرين
    instructor_sessions = defaultdict(list)
    for s in schedules:
        instructor_sessions[s['instructor']].append(s)
    
    for instructor, sessions in instructor_sessions.items():
        by_day = defaultdict(list)
        for s in sessions:
            by_day[s['day']].append(s)
        
        for day, day_sessions in by_day.items():
            sessions_with_minutes = []
            for s in day_sessions:
                start_minutes = time_to_minutes(s['start'])
                end_minutes = time_to_minutes(s['end'])
                sessions_with_minutes.append((start_minutes, end_minutes, s))
            
            sessions_with_minutes.sort(key=lambda x: x[0])
            for i in range(1, len(sessions_with_minutes)):
                prev_start, prev_end, prev_s = sessions_with_minutes[i-1]
                curr_start, curr_end, curr_s = sessions_with_minutes[i]
                if prev_end > curr_start:
                    conflicts["instructor"][instructor].append((prev_s, curr_s))
    
    # نفس المنطق للمجموعات
    group_sessions = defaultdict(list)
    for s in schedules:
        group_sessions[s['group']].append(s)
    
    for group, sessions in group_sessions.items():
        by_day = defaultdict(list)
        for s in sessions:
            by_day[s['day']].append(s)
        
        for day, day_sessions in by_day.items():
            sessions_with_minutes = []
            for s in day_sessions:
                start_minutes = time_to_minutes(s['start'])
                end_minutes = time_to_minutes(s['end'])
                sessions_with_minutes.append((start_minutes, end_minutes, s))
            
            sessions_with_minutes.sort(key=lambda x: x[0])
            for i in range(1, len(sessions_with_minutes)):
                prev_start, prev_end, prev_s = sessions_with_minutes[i-1]
                curr_start, curr_end, curr_s = sessions_with_minutes[i]
                if prev_end > curr_start:
                    conflicts["group"][group].append((prev_s, curr_s))
    
    total_conflicts = (
        sum(len(v) for v in conflicts["room"].values()) +
        sum(len(v) for v in conflicts["instructor"].values()) +
        sum(len(v) for v in conflicts["group"].values())
    )
    logger.info(f"⚠️ تم اكتشاف {total_conflicts} تعارض في الجدول")
    return conflicts

def validate_json_structure(data):
    """التحقق من الهيكل الأساسي لملف JSON"""
    required_sections = ["rooms", "instructors", "groups", "courses"]
    for section in required_sections:
        if section not in data:
            return False, f"القسم المطلوب '{section}' غير موجود"
        if not isinstance(data[section], list):
            return False, f"القسم '{section}' يجب أن يكون قائمة"
    return True, "البنية صالحة"

def validate_room_data(room):
    """التحقق من صحة بيانات القاعة"""
    required_fields = ["id", "name", "type", "capacity"]
    for field in required_fields:
        if field not in room:
            return False, f"حقل '{field}' مفقود في بيانات القاعة"
    valid_types = ["lecture", "lab", "exercise", "نظرية", "عملي", "تمارين"]
    if room["type"] not in valid_types:
        return False, "نوع القاعة يجب أن يكون أحد القيم: lecture, lab, exercise, نظرية, عملي, تمارين"
    if not isinstance(room["capacity"], int) or room["capacity"] <= 0:
        return False, "سعة القاعة يجب أن تكون رقماً صحيحاً موجباً"
    return True, "بيانات القاعة صالحة"

def validate_instructor_data(instructor):
    """التحقق من صحة بيانات المدرس"""
    required_fields = ["id", "name", "expertise", "max_teaching_hours"]
    for field in required_fields:
        if field not in instructor:
            return False, f"حقل '{field}' مفقود في بيانات المدرس"
    if not isinstance(instructor["expertise"], list) or not instructor["expertise"]:
        return False, "يجب تحديد تخصص واحد على الأقل"
    if not isinstance(instructor["max_teaching_hours"], int) or instructor["max_teaching_hours"] <= 0:
        return False, "الحد الأقصى لساعات التدريس يجب أن يكون رقمًا صحيحًا موجبًا"
    return True, "بيانات المدرس صالحة"

def validate_group_data(group):
    """التحقق من صحة بيانات المجموعة"""
    required_fields = ["id", "major", "level", "student_count"]
    for field in required_fields:
        if field not in group:
            return False, f"حقل '{field}' مفقود في بيانات المجموعة"
    if not isinstance(group["level"], int) or group["level"] <= 0:
        return False, "مستوى المجموعة يجب أن يكون رقمًا صحيحًا موجبًا"
    if not isinstance(group["student_count"], int) or group["student_count"] <= 0:
        return False, "عدد الطلاب يجب أن يكون رقمًا صحيحًا موجبًا"
    return True, "بيانات المجموعة صالحة"

def validate_course_data(course):
    """التحقق من صحة بيانات المادة"""
    required_fields = ["id", "name", "group_id", "instructor_id", "duration", "course_type"]
    for field in required_fields:
        if field not in course:
            return False, f"حقل '{field}' مفقود في بيانات المادة"
    valid_types = ["lecture", "lab", "exercise", "نظرية", "عملي", "تمارين"]
    if course["course_type"] not in valid_types:
        return False, "نوع المادة يجب أن يكون أحد القيم: lecture, lab, exercise, نظرية, عملي, تمارين"
    if not isinstance(course["duration"], int) or course["duration"] <= 0:
        return False, "مدة المادة يجب أن تكون رقماً صحيحاً موجباً"
    return True, "بيانات المادة صالحة"


def schedule_with_all_algorithms(data, config=None):
    """
    تنفيذ الجدولة الكاملة (CP-SAT -> SA -> GA) على بيانات المستخدم وإرجاع النتائج لكل مرحلة.
    :param data: dict يحتوي على القاعات والمدرسين والمجموعات والمواد
    :param config: كائن Config أو None (يستخدم الافتراضي إذا لم يُعط)
    :return: dict فيه الجداول الثلاثة: initial, after_sa, after_ga
    """

    logger = logging.getLogger("schedule_with_all_algorithms")
    logger.setLevel(logging.INFO)
    # تحويل البيانات إلى كائنات
    rooms = [Room(**r) for r in data["rooms"]]
    instructors = [Instructor(**i) for i in data["instructors"]]
    groups = [Group(**g) for g in data["groups"]]
    courses = [Course(**c) for c in data["courses"]]
    if config is None:
        config = ModelConfig()
    # 1) الجدولة الأولية
    cp_scheduler = CPSatScheduler(config)
    initial = cp_scheduler.generate_schedule(courses, rooms, groups, instructors)
    # 2) تحسين SA
    sa_optimizer = SoftConstraintsOptimizer(schedules=initial, config=config)
    optimized_sa = sa_optimizer.optimize(max_iters=getattr(config, 'sa_iterations', 100))
    # 3) تحسين GA
    initial_population = [perturb(cp_scheduler) for _ in range(getattr(config, 'population_size', 30))]
    ga = EnhancedGeneticOptimizer(initial_population, config)
    final = ga.evolve()
    # تحويل النتائج إلى DataFrame (اختياري)
    def to_df(schedules):
        rows = []
        for s in schedules:
            rows.append({
                "course": s.assigned_course.name,
                "group": s.group_id,
                "room": s.room_id,
                "instructor": s.assigned_instructor.name,
                "type": s.assigned_course.course_type,
                "day": s.time_slot.day,
                "start": s.time_slot.start_time.strftime("%H:%M"),
                "end": s.time_slot.end_time.strftime("%H:%M"),
                "penalty_score": getattr(s, 'penalty_score', 0)
            })
        return pd.DataFrame(rows)
    return {
        "initial": initial,
        "after_sa": optimized_sa,
        "after_ga": final,
        "initial_df": to_df(initial),
        "after_sa_df": to_df(optimized_sa),
        "after_ga_df": to_df(final)
    }

