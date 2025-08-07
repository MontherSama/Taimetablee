import copy
import logging
from collections import defaultdict
from ortools.sat.python import cp_model
from typing import Dict, List, Any
from datetime import time

from model import Schedule, TimeSlot, Config, Course, Room, Group, Instructor, DayOfWeek

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class CPSatScheduler:
    """محرك الجدولة باستخدام CP-SAT مع تصميم معياري وحقن تبعيات"""
    
    def __init__(self, config: Config):
        self.config = config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.variables: Dict[str, Dict[str, Any]] = {}
        self.rooms: List[Room] = []
        self.groups: Dict[str, Group] = {}  # تخزين المجموعات في قاموس للوصول السريع
        self.instructors: List[Instructor] = []
        self.split_course_map: Dict[str, List[Course]] = defaultdict(list)
        self.rotation_groups: Dict[str, List[Course]] = defaultdict(list)

    def generate_schedule(
        self,
        courses: List[Course],
        rooms: List[Room],
        groups: List[Group],
        instructors: List[Instructor]
    ) -> List[Schedule]:
        logger.info("🚀 بدء جدولة CP-SAT...")
        try:
            self.rooms = copy.deepcopy(rooms)
            self.groups = {g.id: g for g in copy.deepcopy(groups)}
            self.instructors = copy.deepcopy(instructors)
            
            # معالجة مسبقة للمواد وإنشاء المجموعات الفرعية
            processed_courses = self._preprocess_courses(courses)
            logger.info(f"📚 عدد المواد بعد المعالجة: {len(processed_courses)}")
            
            # إنشاء متغيرات القرار
            self._create_decision_variables(processed_courses)
            
            # إضافة القيود
            self._add_room_constraints(processed_courses)
            self._add_instructor_constraints(processed_courses)
            self._add_group_constraints(processed_courses)
            self._add_time_constraints(processed_courses)
            self._add_rotation_constraints(processed_courses)
            
            # حل النموذج مع معلمات متقدمة
            self.solver.parameters.max_time_in_seconds = 60.0  # زيادة وقت البحث
            self.solver.parameters.num_search_workers = 8       # استخدام كل الأنوية
            self.solver.parameters.log_search_progress = True   # تسجيل تقدم البحث
            
            status = self.solver.Solve(self.model)
            logger.info(f"📊 حالة المحلّل: {self.solver.StatusName(status)}")
            
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                self._analyze_infeasibility(processed_courses)
                return []
            
            # استخراج الجدول
            return self._extract_schedule(status, processed_courses)
        except Exception as e:
            logger.error(f"❌ خطأ أثناء توليد الجدول: {e}", exc_info=True)
            return []


    def _preprocess_courses(self, courses: List[Course]) -> List[Course]:
        """
        معالجة المواد: تقسيم المواد حسب الحاجة، وتحديث المجموعات الفرعية.
        """
        expanded = []
        groups_copy = {k: copy.deepcopy(v) for k, v in self.groups.items()}
        for c in courses:
            try:
                logger.debug(f"🔍 معالجة المادة: {c.id} ({c.name})")
                suitable_rooms = self._get_suitable_rooms(c)
                group = groups_copy[c.group_id]
                if self._needs_splitting(c, suitable_rooms, group):
                    subgroups = self._split_course(c, group, suitable_rooms, groups_copy)
                    expanded.extend(subgroups)
                    self.split_course_map[c.id] = subgroups
                    logger.info(f"📦 تم تقسيم {c.name} إلى {len(subgroups)} أقسام")
                    if c.course_type == "عملي" and getattr(c, "rotation_group", None):
                        self.rotation_groups[c.rotation_group].extend(subgroups)
                else:
                    expanded.append(c)
                    logger.debug(f"✅ المادة {c.name} لا تحتاج لتقسيم")
            except Exception as e:
                logger.error(f"❌ خطأ في معالجة المادة {c.id}: {e}", exc_info=True)
        self.groups.update(groups_copy)
        return expanded

    def _get_suitable_rooms(self, course: Course) -> List[Room]:
        """
        استخراج القاعات المناسبة للمادة.
        """
        try:
            suitable = [
                r for r in self.rooms
                if r.type == course.course_type
                and (not course.required_facilities or all(f in r.facilities for f in course.required_facilities))
            ]
            logger.debug(f"🔎 {len(suitable)} قاعات مناسبة للمادة {course.id}")
            return suitable
        except Exception as e:
            logger.error(f"❌ خطأ في استخراج القاعات المناسبة للمادة {course.id}: {e}")
            return []

    def _find_group(self, group_id: str) -> Group:
        """
        البحث عن مجموعة حسب المعرف.
        """
        try:
            return self.groups[group_id]
        except KeyError:
            raise ValueError(f"Group not found: {group_id}")

    def _needs_splitting(self, course: Course, suitable_rooms: List[Room], group: Group) -> bool:
        """
        تحديد إذا كانت المادة تحتاج تقسيم بناءً على القاعات والمجموعة.
        """
        try:
            if course.can_merge:
                logger.debug(f"🔄 المادة {course.id} قابلة للدمج - لا تحتاج للتقسيم")
                return False
            if not suitable_rooms:
                logger.warning(f"⚠️ لا توجد قاعة مناسبة للمادة {course.id} - سيتم تقسيمها")
                return True
            max_capacity = max(r.capacity for r in suitable_rooms)
            if max_capacity < group.student_count:
                logger.warning(f"⚠️ لا توجد قاعة كافية للمادة {course.id} - سيتم تقسيمها")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ خطأ في تحديد تقسيم المادة {course.id}: {e}")
            return False
            if not suitable_rooms:
                logger.warning(f"⚠️ لا توجد قاعة مناسبة للمادة {course.id} - سيتم تقسيمها")
                return True
                
            # إذا كانت أكبر قاعة لا تستوعب المجموعة
            max_capacity = max(r.capacity for r in suitable_rooms)
            if max_capacity < group.student_count:
                logger.warning(f"⚠️ لا توجد قاعة كافية للمادة {course.id} - سيتم تقسيمها")
                return True
                
            return False
        except Exception as e:
            logger.error(f"❌ خطأ في تحديد تقسيم المادة {course.id}: {e}")
            return False

    def _split_course(self, course: Course, group: Group, suitable_rooms: List[Room], groups: Dict[str, Group]) -> List[Course]:
        """
        تقسيم المادة إلى أقسام فرعية حسب سعة القاعات وتوزيع الطلاب.
        """
        try:
            max_cap = max(r.capacity for r in suitable_rooms) if suitable_rooms else group.student_count
            student_count = group.student_count
            count = max(1, (student_count + max_cap - 1) // max_cap)
            subgroups = []
            remaining = student_count
            for i in range(count):
                part_size = min(max_cap, remaining)
                subgroup_id = f"{group.id}_sub{i+1}"
                if subgroup_id not in groups:
                    sub_group = copy.deepcopy(group)
                    sub_group.id = subgroup_id
                    sub_group.student_count = part_size
                    groups[subgroup_id] = sub_group
                else:
                    sub_group = groups[subgroup_id]
                remaining -= part_size
                sub = copy.deepcopy(course)
                sub.id = f"{course.id}_sub{i+1}"
                sub.name = f"{course.name} (قسم {i+1})"
                sub.group_id = subgroup_id
                subgroups.append(sub)
            return subgroups
        except Exception as e:
            logger.error(f"❌ خطأ في تقسيم المادة {course.id}: {e}")
            return [course]
   
    def _create_decision_variables(self, courses: List[Course]):
        for c in courses:
            try:
                cid = c.id
                duration = c.duration
                
                # نطاق وقت الجدولة (بالدقائق)
                max_time = 7 * 24 * 60 - 1
                
                # متغيرات القرار
                start = self.model.NewIntVar(0, max_time, f'start_{cid}')
                end = self.model.NewIntVar(0, max_time + duration, f'end_{cid}')
                room = self.model.NewIntVar(0, len(self.rooms) - 1, f'room_{cid}')
                instr = self.model.NewIntVar(0, len(self.instructors) - 1, f'instr_{cid}')
                interval = self.model.NewIntervalVar(start, duration, end, f'iv_{cid}')
                
                # تخزين المتغيرات
                self.variables[cid] = {
                    'start': start,
                    'end': end,
                    'room': room,
                    'instr': instr,
                    'interval': interval,
                    'course': c
                }
                
                logger.debug(f"➕ تم إنشاء متغيرات للمادة: {c.name}")
            except Exception as e:
                logger.error(f"❌ خطأ في إنشاء متغيرات القرار للمادة {c.id}: {e}")

    def _add_room_constraints(self, courses: List[Course]):
        room_intervals = defaultdict(list)
        
        for c in courses:
            cid = c.id
            if cid not in self.variables:
                continue
                
            v = self.variables[cid]
            group = self._find_group(c.group_id)
            
            # القاعات المناسبة لهذه المادة
            suitable_idxs = [
                i for i, r in enumerate(self.rooms)
                if r.type == c.course_type 
                and r.capacity >= group.student_count
                and (not c.required_facilities or 
                     all(f in r.facilities for f in c.required_facilities))
            ]
            
            if not suitable_idxs:
                logger.error(f"❌ لا توجد قاعة مناسبة للمادة {c.name}")
                continue
                
            # إضافة قيود تعيين القاعة
            self.model.AddAllowedAssignments([v['room']], [(i,) for i in suitable_idxs])
            
            # إضافة قيود عدم التداخل
            for ridx in suitable_idxs:
                b = self.model.NewBoolVar(f'room_assign_{cid}_{ridx}')
                self.model.Add(v['room'] == ridx).OnlyEnforceIf(b)
                self.model.Add(v['room'] != ridx).OnlyEnforceIf(b.Not())
                
                iv = self.model.NewOptionalIntervalVar(
                    v['start'], c.duration, v['end'], b, f'opt_iv_{cid}_{ridx}')
                room_intervals[ridx].append(iv)
        
        # قيد عدم التداخل لكل قاعة
        for idx, ivs in room_intervals.items():
            if ivs:
                self.model.AddNoOverlap(ivs)
                logger.debug(f"🚫 تم إضافة قيد عدم التداخل للقاعة: {self.rooms[idx].name}")

    def _add_instructor_constraints(self, courses: List[Course]):
        instr_intervals = defaultdict(list)
        
        for c in courses:
            cid = c.id
            if cid not in self.variables:
                continue
                
            v = self.variables[cid]
            
            try:
                # البحث عن المدرس المناسب
                instructor = next(inst for inst in self.instructors if inst.id == c.instructor_id)
                idx = self.instructors.index(instructor)
                
                # التحقق من تخصص المدرس
                if c.course_type not in instructor.expertise:
                    logger.error(f"❌ المدرس {instructor.name} ليس متخصصًا في نوع المادة {c.course_type}")
                    continue
                
                # إضافة قيد تعيين المدرس
                self.model.Add(v['instr'] == idx)
                
                # تسجيل الفترة الزمنية للمدرس
                instr_intervals[idx].append(v['interval'])
            except StopIteration:
                logger.error(f"❌ مدرس غير موجود: {c.instructor_id}")
            except Exception as e:
                logger.error(f"❌ خطأ في إضافة قيود المدرس للمادة {c.id}: {e}")
        
        # قيد عدم التداخل لكل مدرس
        for idx, ivs in instr_intervals.items():
            if ivs:
                self.model.AddNoOverlap(ivs)
                logger.debug(f"👨‍🏫 تم إضافة قيود عدم التداخل للمدرس: {self.instructors[idx].name}")

    def _add_group_constraints(self, courses: List[Course]):
        # قيود على مستوى المجموعة الأصلية
        base_grp_intervals = defaultdict(list)
        # قيود على مستوى الأقسام الفرعية
        subgroup_intervals = defaultdict(list)
        # ربط الأبناء مع الأب
        parent_to_subgroups = defaultdict(list)

        # فصل المواد النظرية والعملية
        theory_courses = []
        lab_courses = []

        for c in courses:
            if '_sub' not in c.id:
                theory_courses.append(c)
            else:
                lab_courses.append(c)

        # جمع الفترات الزمنية لكل مجموعة أصلية وأبنائها
        for c in theory_courses:
            if c.id not in self.variables:
                continue
            v = self.variables[c.id]
            base_group_id = c.group_id.split('_')[0] if '_sub' in c.group_id else c.group_id
            base_grp_intervals[base_group_id].append(v['interval'])

        for c in lab_courses:
            if c.id not in self.variables:
                continue
            v = self.variables[c.id]
            # استخراج معرف المجموعة الأصلية
            parent_group_id = c.group_id.split('_sub')[0] if '_sub' in c.group_id else c.group_id
            subgroup_intervals[c.group_id].append(v['interval'])
            parent_to_subgroups[parent_group_id].append(v['interval'])

        # قيود عدم التداخل للمواد النظرية (للمجموعة كاملة)
        for grp_id, ivs in base_grp_intervals.items():
            if ivs:
                self.model.AddNoOverlap(ivs)
                logger.debug(f"👥 تم إضافة قيود عدم التداخل للمجموعة الأصلية: {grp_id}")

        # قيود الأقسام الفرعية (لكل قسم على حدة)
        for grp_id, ivs in subgroup_intervals.items():
            if ivs:
                self.model.AddNoOverlap(ivs)
                logger.debug(f"👥 تم إضافة قيود عدم التداخل للقسم الفرعي: {grp_id}")

        # إضافة قيد عدم التداخل بين الأب وجميع الأبناء
        for parent_id in base_grp_intervals:
            parent_intervals = base_grp_intervals[parent_id]
            sub_intervals = parent_to_subgroups.get(parent_id, [])
            if parent_intervals and sub_intervals:
                self.model.AddNoOverlap(parent_intervals + sub_intervals)
                logger.debug(f"� تم إضافة قيد عدم التداخل بين الأب ({parent_id}) وجميع الأبناء")

    def _add_time_constraints(self, courses: List[Course]):
        daily_start = self._time_to_minutes(self.config.daily_start_time)
        daily_end = self._time_to_minutes(self.config.daily_end_time)
        # days as int (0=Saturday, ...)
        working_days = [d.value if hasattr(d, 'value') else int(d) for d in self.config.working_days]
        for c in courses:
            cid = c.id
            if cid not in self.variables:
                continue
            v = self.variables[cid]
            # حساب الوقت ضمن اليوم
            mod = self.model.NewIntVar(daily_start, daily_end-1, f'mod_{cid}')
            self.model.AddModuloEquality(mod, v['start'], 24*60)
            # القيود اليومية
            self.model.Add(mod >= daily_start)
            self.model.Add(mod + c.duration <= daily_end)
            # أيام العمل
            day = self.model.NewIntVarFromDomain(cp_model.Domain.FromValues(working_days), f'day_{cid}')
            self.model.AddDivisionEquality(day, v['start'], 24*60)
            # قيد صارم: لا يُسمح إلا بالأيام المسموحة فقط
            self.model.AddAllowedAssignments([day], [(d,) for d in working_days])
            logger.debug(f"⏰ تم إضافة قيود زمنية للمادة: {c.name}")

    def _time_to_minutes(self, t: time) -> int:
        return t.hour * 60 + t.minute

    def _add_rotation_constraints(self, courses: List[Course]):
        """إضافة قيود التناوب للمواد العملية"""
        # 1. قيود التناوب المباشرة بين الأقسام
        for rotation_group, lab_courses in self.rotation_groups.items():
            if len(lab_courses) < 2:
                continue
                
            # إنشاء أزواج التناوب (نظام التبادل)
            for i in range(len(lab_courses)):
                for j in range(i+1, len(lab_courses)):
                    c1 = lab_courses[i]
                    c2 = lab_courses[j]
                    
                    # فقط إذا كانت من نفس مجموعة التدوير ولكن مواد مختلفة
                    if c1.rotation_group == c2.rotation_group and c1.id.split('_')[0] != c2.id.split('_')[0]:
                        v1 = self.variables[c1.id]
                        v2 = self.variables[c2.id]
                        
                        # قيد التناوب: يجب أن تكون المواد في نفس الوقت
                        self.model.Add(v1['start'] == v2['start'])
                        logger.debug(f"🔄 تم إضافة قيد تدوير بين {c1.name} و {c2.name}")
        
        # 2. قيود ترتيب المواد: نظرية أولاً ثم عملية
        theory_courses = [c for c in courses if '_sub' not in c.id and c.course_type == "نظرية"]
        lab_courses = [c for c in courses if c.course_type == "عملي"]
        
        for theory_c in theory_courses:
            if theory_c.id not in self.variables:
                continue
                
            v_theory = self.variables[theory_c.id]
            base_group_id = theory_c.group_id.split('_')[0] if '_sub' in theory_c.group_id else theory_c.group_id
            
            for lab_c in lab_courses:
                if lab_c.id not in self.variables:
                    continue
                    
                # فقط إذا كانت لنفس المجموعة الأصلية
                lab_base_group = lab_c.group_id.split('_')[0] if '_sub' in lab_c.group_id else lab_c.group_id
                if lab_base_group == base_group_id:
                    v_lab = self.variables[lab_c.id]
                    self.model.Add(v_lab['start'] >= v_theory['end'])
                    logger.debug(f"⏱ تم إضافة قيد ترتيب: {theory_c.name} قبل {lab_c.name}")

    def _analyze_infeasibility(self, courses: List[Course]):
        """تحليل متقدم لأسباب عدم إمكانية الجدولة"""
        logger.error("🔍 بدء التحليل المتقدم لعدم إمكانية الجدولة:")
        
        # 1. التحقق من توفر الوقت الكافي
        total_duration = sum(c.duration for c in courses)
        
        # حساب الوقت اليومي الفعلي
        daily_diff = (self._time_to_minutes(self.config.daily_end_time) - 
                     self._time_to_minutes(self.config.daily_start_time))
        
        # حساب الوقت المتاح الإجمالي
        working_minutes = len(self.config.working_days) * daily_diff
        
        logger.error(f" - إجمالي وقت المحاضرات: {total_duration} دقيقة")
        logger.error(f" - الوقت اليومي المتاح: {daily_diff} دقيقة")
        logger.error(f" - عدد أيام العمل: {len(self.config.working_days)} يوم")
        logger.error(f" - الوقت المتاح الإجمالي: {working_minutes} دقيقة")
        
        # 2. تحليل القاعات
        for room in self.rooms:
            room_usage = 0
            for c in courses:
                if c.course_type == room.type:
                    room_usage += c.duration
            logger.error(f" - القاعة {room.name}: السعة {room.capacity}، الاستخدام {room_usage} دقيقة")
        
        # 3. تحليل عبء المدرسين
        for instr in self.instructors:
            teaching_time = 0
            for c in courses:
                if c.instructor_id == instr.id:
                    teaching_time += c.duration
            max_minutes = instr.max_teaching_hours * 60
            logger.error(f" - المدرس {instr.name}: وقت التدريس {teaching_time} دقيقة (الحد الأقصى {max_minutes})")
            
            # التحقق من التخصص
            for c in courses:
                if c.instructor_id == instr.id:
                    if c.course_type == "عملي" and "عملي" not in instr.expertise:
                        logger.error(f"   ❌ المدرس {instr.name} ليس متخصصًا في المواد العملية لكنه مسجل للمادة العملية {c.name}")
                    elif c.course_type == "نظرية" and "نظرية" not in instr.expertise:
                        logger.error(f"   ❌ المدرس {instr.name} ليس متخصصًا في المواد النظرية لكنه مسجل للمادة النظرية {c.name}")
        
        # 4. اقتراح حلول
        if total_duration > working_minutes:
            logger.error("✅ الحل المقترح: زيادة أيام العمل أو ساعات العمل اليومية")
        elif any(instr.max_teaching_hours * 60 < teaching_time for instr in self.instructors):
            logger.error("✅ الحل المقترح: توزيع المواد على مدرسين إضافيين")
        else:
            logger.error("✅ الحل المقترح: مراجعة القيود التالية:")
            logger.error("   - تعارض تخصصات المدرسين")
            logger.error("   - تعارض في أوقات الجدولة")
            logger.error("   - قيود غير منطقية في البيانات")

    def _extract_schedule(self, status: int, courses: List[Course]) -> List[Schedule]:
        """
        استخراج الجدول النهائي من النموذج
        """
        result = []
        for c in courses:
            try:
                if c.id not in self.variables:
                    logger.warning(f"⚠️ لا يوجد جدول للمادة: {c.id}")
                    continue
                    
                sched = self._create_schedule_entry(c)
                result.append(sched)
            except Exception as e:
                logger.error(f"❌ خطأ في استخراج الجدول للمادة {c.id}: {e}")
        return result

    def _create_schedule_entry(self, course: Course) -> Schedule:

        try:
            vals = self.variables[course.id]
            st_minutes = self.solver.Value(vals['start'])
            room_idx = self.solver.Value(vals['room'])
            instr_idx = self.solver.Value(vals['instr'])
            
            room = self.rooms[room_idx]
            instructor = self.instructors[instr_idx]
            group = self._find_group(course.group_id)
            
            # حساب اليوم ووقت البدء
            day_int = st_minutes // (24 * 60)
            mins_in_day = st_minutes % (24 * 60)
            
            start_time = time(mins_in_day // 60, mins_in_day % 60)
            end_time = time((mins_in_day + course.duration) // 60, 
                           (mins_in_day + course.duration) % 60)
            
            # إنشاء الفترة الزمنية
            time_slot = TimeSlot(
                day=DayOfWeek.from_int(day_int),
                start_time=start_time,
                end_time=end_time
            )
            
            # إنشاء الجدول
            return Schedule(
                course_id=course.id,
                room_id=room.id,
                instructor_id=instructor.id,
                time_slot=time_slot,
                group_id=course.group_id,
                assigned_course=course,
                assigned_room=room,
                assigned_instructor=instructor,
                assigned_group=group
            )
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء مدخل الجدول للمادة {course.id}: {e}")
            raise

def analyze_feasibility(courses, rooms, groups, instructors, working_days, daily_start_time, daily_end_time, logger=print):
    """
    تحليل رياضي دقيق لمتطلبات الجدولة مقابل الموارد المتاحة.
    يطبع تقريراً مفصلاً عن سبب عدم القدرة على الجدولة واقتراحات الحلول.
    """
    from collections import defaultdict
    import math
    # حساب عدد الدقائق المتاحة لكل قاعة
    day_minutes = (daily_end_time.hour * 60 + daily_end_time.minute) - (daily_start_time.hour * 60 + daily_start_time.minute)
    total_days = len(working_days)
    total_room_minutes = defaultdict(int)
    for r in rooms:
        total_room_minutes[r.id] = day_minutes * total_days

    # حساب عدد الدقائق المطلوبة لكل نوع قاعة
    required_room_minutes = defaultdict(int)
    required_by_room = defaultdict(list)
    for c in courses:
        # حدد نوع القاعة المطلوبة
        room_type = c.course_type
        # ابحث عن القاعات المناسبة
        suitable_rooms = [r for r in rooms if r.type == room_type and (not c.required_facilities or all(f in r.facilities for f in c.required_facilities))]
        if not suitable_rooms:
            logger(f"❌ المادة {c.name} ({c.id}) تحتاج قاعة من نوع {room_type} بمواصفات {c.required_facilities} ولا توجد قاعة مناسبة.")
        # حساب عدد الأقسام المطلوبة إذا حجم المجموعة أكبر من سعة القاعة
        group = next((g for g in groups if g.id == c.group_id), None)
        if group:
            max_cap = max([r.capacity for r in suitable_rooms], default=0)
            n_sections = max(1, math.ceil(group.student_count / max_cap)) if max_cap > 0 else 1
            for i in range(n_sections):
                required_room_minutes[room_type] += c.duration
                required_by_room[room_type].append((c.name, c.duration, group.id, group.student_count, max_cap))
        else:
            required_room_minutes[room_type] += c.duration
            required_by_room[room_type].append((c.name, c.duration, c.group_id, 'N/A', 'N/A'))

    logger("\n===== تقرير الجدولة الرياضي =====")
    logger(f"عدد الأيام المسموحة: {total_days} ({working_days})")
    logger(f"عدد الدقائق المتاحة في اليوم: {day_minutes}")
    logger(f"عدد القاعات: {len(rooms)}")
    for r in rooms:
        logger(f"- {r.name} (نوع: {r.type}, سعة: {r.capacity}) => {total_room_minutes[r.id]} دقيقة متاحة")
    logger("\n--- المتطلبات حسب نوع القاعة ---")
    for room_type in set(r.type for r in rooms):
        total_available = sum(total_room_minutes[r.id] for r in rooms if r.type == room_type)
        total_required = required_room_minutes[room_type]
        logger(f"نوع القاعة: {room_type}")
        logger(f"  - الدقائق المطلوبة: {total_required}")
        logger(f"  - الدقائق المتاحة: {total_available}")
        if total_required > total_available:
            logger(f"  ❌ النقص: {total_required - total_available} دقيقة. يجب زيادة عدد القاعات أو الأيام أو تقليل عدد المواد/المدة.")
        else:
            logger(f"  ✅ الموارد كافية.")
    logger("\n--- تفاصيل المواد ---")
    for room_type, lst in required_by_room.items():
        logger(f"مواد تحتاج {room_type}:")
        for name, duration, group_id, group_size, max_cap in lst:
            logger(f"  - {name} (مجموعة: {group_id}, مدة: {duration}د، حجم: {group_size}، أكبر قاعة: {max_cap})")
    logger("\n--- تحليل المدرسين ---")
    # حساب ساعات التدريس المطلوبة لكل مدرس
    instr_hours = defaultdict(int)
    for c in courses:
        instr_hours[c.instructor_id] += c.duration
    for i in instructors:
        logger(f"- {i.name}: مطلوب {instr_hours[i.id]//60} ساعة، الحد الأقصى {i.max_teaching_hours} ساعة.")
        if instr_hours[i.id] > i.max_teaching_hours * 60:
            logger(f"  ❌ المدرس {i.name} يحتاج زيادة الحد الأقصى أو تقليل المواد.")
    logger("\n--- تحليل المجموعات ---")
    group_minutes = defaultdict(int)
    for c in courses:
        group_minutes[c.group_id] += c.duration
    for g in groups:
        logger(f"- {g.id}: مطلوب {group_minutes[g.id]//60} ساعة، عدد الأيام {total_days}")
        if group_minutes[g.id] > total_days * day_minutes:
            logger(f"  ❌ المجموعة {g.id} تحتاج زيادة الأيام أو تقليل المواد.")
    logger("\n===== نهاية التقرير =====\n")
    return