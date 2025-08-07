import logging
import random
from copy import deepcopy
import time as systime
from typing import List, Dict, Tuple, Any
from collections import defaultdict
import statistics
from datetime import time

from model import Schedule, TimeSlot, Config, Course, Room, Group, Instructor, DayOfWeek
from algorithm.soft_constraints_validator import SoftConstraintsValidator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class EnhancedGeneticOptimizer:
    """خوارزمية وراثية متقدمة لتحسين الجدول مع مراعاة القيود المرنة"""
    
    def __init__(self, initial_schedules: List[List[Schedule]], config: Config):
        """
        تهيئة المحسن الوراثي
        
        Args:
            initial_schedules: قائمة من الجداول الأولية (حلول أولية)
            config: إعدادات التطبيق (تحتوي على أوزان القيود المرنة)
        """
        self.config = config
        self.population = initial_schedules
        self.validator = SoftConstraintsValidator(config)
        self.fitness_cache = {}
        self.diversity_history = []
        self.best_fitness_history = []
        self.best_schedule = None
        
        # معلمات الخوارزمية (قابلة للتخصيص)
        self.population_size = config.ga_params.get("population_size", 100)
        self.generations = config.ga_params.get("generations", 100)
        self.crossover_rate = config.ga_params.get("crossover_rate", 0.85)
        self.mutation_rate = config.ga_params.get("mutation_rate", 0.15)
        self.elitism_count = config.ga_params.get("elitism_count", 5)
        self.island_count = config.ga_params.get("island_count", 4)
        self.migration_rate = config.ga_params.get("migration_rate", 0.1)
        
        # أوزان القيود المرنة (من config أو افتراضية)
        self.weights = config.ga_params.get("penalty_weights", {
            "room_conflict": 10000,
            "instructor_conflict": 20000,
            "group_conflict": 15000,
            "facility_mismatch": 50,
            "time_preference": 30,
            "minimize_gaps": 10,
            "balance_room_usage": 5,
            "merge_bonus": -50  # مكافأة (تطرح من العقوبة)
        })
        
        # استراتيجيات الطفرة وأوزانها
        self.mutation_strategies = [
            self._mutate_time_shift,
            self._mutate_room_swap,
            self._mutate_instructor_swap,
            self._mutate_day_rotation
        ]
        self.mutation_weights = [0.3, 0.3, 0.2, 0.2]  # أوزان نسبية
        
        # إنشاء نموذج الجزر
        self.islands = self._create_islands()
        
    def _create_islands(self) -> List[List[List[Schedule]]]:
        """تقسيم السكان إلى جزر معزولة"""
        islands = [[] for _ in range(self.island_count)]
        for i, schedule in enumerate(self.population):
            islands[i % self.island_count].append(schedule)
        return islands

    def _fitness(self, schedule: List[Schedule]) -> float:
        """حساب اللياقة للجدول (كلما ارتفعت كلما كان أفضل)"""
        # استخدام ذاكرة التخزين المؤقت إذا كان الجدول قد تم تقييمه مسبقًا
        schedule_hash = hash(tuple((s.course_id, s.time_slot.start_minutes, s.room_id) for s in schedule))
        if schedule_hash in self.fitness_cache:
            return self.fitness_cache[schedule_hash]
        
        # حساب العقوبة الإجمالية
        total_penalty = self.validator.penalty(schedule)
        
        # تطبيق الأوزان المخصصة
        weighted_penalty = 0
        for constraint, penalty_value in total_penalty.items():
            weight = self.weights.get(constraint, 1.0)
            weighted_penalty += weight * penalty_value
        
        # اللياقة = 1 / (1 + weighted_penalty) لتكون بين 0 و1
        fitness = 1.0 / (1.0 + weighted_penalty)
        
        # التخزين المؤقت
        self.fitness_cache[schedule_hash] = fitness
        return fitness

    def _select_parents(self, island: List[List[Schedule]]) -> Tuple[List[Schedule], List[Schedule]]:
        """اختيار أبوين من الجزيرة باستخدام بطولة"""
        tournament_size = min(5, len(island))
        tournament = random.sample(island, tournament_size)
        tournament.sort(key=self._fitness, reverse=True)
        return tournament[0], tournament[1]

    def _crossover(self, parent1: List[Schedule], parent2: List[Schedule]) -> List[Schedule]:
        """تهجين بين أبوين لإنتاج طفل"""
        # استراتيجيات التهجين المختلفة
        if random.random() < 0.7:
            return self._uniform_crossover(parent1, parent2)
        else:
            return self._multi_point_crossover(parent1, parent2)

    def _uniform_crossover(self, parent1: List[Schedule], parent2: List[Schedule]) -> List[Schedule]:
        """تهجين موحد: اختيار جلسات عشوائية من الأبوين"""
        child = []
        for i in range(len(parent1)):
            if random.random() < 0.5:
                child.append(deepcopy(parent1[i]))
            else:
                child.append(deepcopy(parent2[i]))
        return child

    def _multi_point_crossover(self, parent1: List[Schedule], parent2: List[Schedule]) -> List[Schedule]:
        """تهجين متعدد النقاط"""
        points = sorted(random.sample(range(1, len(parent1)), random.randint(1, 3)))
        child = []
        start = 0
        use_parent1 = True
        
        for point in points:
            if use_parent1:
                child.extend(deepcopy(parent1[start:point]))
            else:
                child.extend(deepcopy(parent2[start:point]))
            start = point
            use_parent1 = not use_parent1
        
        # الجزء الأخير
        if use_parent1:
            child.extend(deepcopy(parent1[start:]))
        else:
            child.extend(deepcopy(parent2[start:]))
        
        return child

    def _mutate(self, schedule: List[Schedule]) -> List[Schedule]:
        """تطبيق طفرات على الجدول"""
        # اختيار استراتيجية طفرة حسب الأوزان
        mutation_strategy = random.choices(
            self.mutation_strategies,
            weights=self.mutation_weights,
            k=1
        )[0]
        
        return mutation_strategy(schedule)

    def _mutate_time_shift(self, schedule: List[Schedule]) -> List[Schedule]:
        """طفرة بتغيير وقت جلسة عشوائية مع الالتزام الصارم بالأيام وساعات العمل فقط"""
        mutated = deepcopy(schedule)
        idx = random.randint(0, len(mutated) - 1)
        session = mutated[idx]
        # استخراج اليوم الحالي
        allowed_days = [d.value if hasattr(d, 'value') else int(d) for d in self.config.working_days]
        current_day = session.time_slot.day.value if hasattr(session.time_slot.day, 'value') else int(session.time_slot.day)
        # إذا اليوم غير مسموح، اختر يوم مسموح عشوائي
        if current_day not in allowed_days:
            current_day = random.choice(allowed_days)
        # حدود اليوم
        daily_start = self.config.daily_start_time.hour * 60 + self.config.daily_start_time.minute
        daily_end = self.config.daily_end_time.hour * 60 + self.config.daily_end_time.minute
        # تغيير الوقت ضمن اليوم فقط
        max_shift = min(60, daily_end - daily_start - session.time_slot.duration)
        shift = random.randint(-max_shift, max_shift)
        old_start = session.time_slot.start_minutes % (24*60)
        new_start = old_start + shift
        # ضبط ضمن الحدود
        if new_start < daily_start:
            new_start = daily_start
        if new_start + session.time_slot.duration > daily_end:
            new_start = daily_end - session.time_slot.duration
        # إعادة تعيين الوقت
        abs_start = current_day * 24*60 + new_start
        abs_end = abs_start + session.time_slot.duration
        session.time_slot.start_minutes = abs_start
        session.time_slot.end_minutes = abs_end
        session.time_slot.start_time = time(new_start // 60, new_start % 60)
        session.time_slot.end_time = time((new_start + session.time_slot.duration) // 60, (new_start + session.time_slot.duration) % 60)
        # اليوم يجب أن يكون من نوع DayOfWeek أو من الأيام المسموحة فقط
        if hasattr(DayOfWeek, '__members__'):
            session.time_slot.day = DayOfWeek(current_day)
        else:
            session.time_slot.day = current_day
        return mutated

    def _mutate_room_swap(self, schedule: List[Schedule]) -> List[Schedule]:
        """طفرة بتبديل قاعة جلسة عشوائية"""
        mutated = deepcopy(schedule)
        idx = random.randint(0, len(mutated) - 1)
        session = mutated[idx]
        
        # البحث عن قاعة مناسبة
        suitable_rooms = [
            room for room in self.config.rooms
            if room.type == session.assigned_course.course_type
            and room.capacity >= session.assigned_group.student_count
            and (session.assigned_course.required_facilities is None or 
                 all(f in room.facilities for f in session.assigned_course.required_facilities))
        ]
        
        if suitable_rooms:
            new_room = random.choice(suitable_rooms)
            session.room_id = new_room.id
            session.assigned_room = new_room
        
        return mutated

    def _mutate_instructor_swap(self, schedule: List[Schedule]) -> List[Schedule]:
        """طفرة بتبديل مدرس جلسة عشوائية"""
        mutated = deepcopy(schedule)
        idx = random.randint(0, len(mutated) - 1)
        session = mutated[idx]
        
        # البحث عن مدرسين بديلين مناسبين
        suitable_instructors = [
            inst for inst in self.config.instructors
            if inst.id != session.instructor_id
            and session.assigned_course.course_type in inst.expertise
        ]
        
        if suitable_instructors:
            new_instructor = random.choice(suitable_instructors)
            session.instructor_id = new_instructor.id
            session.assigned_instructor = new_instructor
        
        return mutated

    def _mutate_day_rotation(self, schedule: List[Schedule]) -> List[Schedule]:
        """طفرة بتغيير يوم جلسة عشوائية مع الالتزام الصارم بالأيام المسموحة وساعات العمل فقط"""
        mutated = deepcopy(schedule)
        idx = random.randint(0, len(mutated) - 1)
        session = mutated[idx]
        allowed_days = [d.value if hasattr(d, 'value') else int(d) for d in self.config.working_days]
        current_day = session.time_slot.day.value if hasattr(session.time_slot.day, 'value') else int(session.time_slot.day)
        possible_days = [d for d in allowed_days if d != current_day]
        if possible_days:
            new_day = random.choice(possible_days)
            # التأكد أن الوقت ضمن ساعات العمل
            daily_start = self.config.daily_start_time.hour * 60 + self.config.daily_start_time.minute
            daily_end = self.config.daily_end_time.hour * 60 + self.config.daily_end_time.minute
            start_in_day = session.time_slot.start_minutes % (24*60)
            # إذا الوقت خارج النطاق، ضبطه
            if start_in_day < daily_start:
                start_in_day = daily_start
            if start_in_day + session.time_slot.duration > daily_end:
                start_in_day = daily_end - session.time_slot.duration
            abs_start = new_day * 24*60 + start_in_day
            abs_end = abs_start + session.time_slot.duration
            if hasattr(DayOfWeek, '__members__'):
                session.time_slot.day = DayOfWeek(new_day)
            else:
                session.time_slot.day = new_day
            session.time_slot.start_minutes = abs_start
            session.time_slot.end_minutes = abs_end
            session.time_slot.start_time = time(start_in_day // 60, start_in_day % 60)
            session.time_slot.end_time = time((start_in_day + session.time_slot.duration) // 60, (start_in_day + session.time_slot.duration) % 60)
        else:
            # إذا لم يوجد يوم بديل، ثبّت اليوم الحالي على أول يوم مسموح
            if allowed_days:
                new_day = allowed_days[0]
                daily_start = self.config.daily_start_time.hour * 60 + self.config.daily_start_time.minute
                abs_start = new_day * 24*60 + daily_start
                abs_end = abs_start + session.time_slot.duration
                if hasattr(DayOfWeek, '__members__'):
                    session.time_slot.day = DayOfWeek(new_day)
                else:
                    session.time_slot.day = new_day
                session.time_slot.start_minutes = abs_start
                session.time_slot.end_minutes = abs_end
                session.time_slot.start_time = time(daily_start // 60, daily_start % 60)
                session.time_slot.end_time = time((daily_start + session.time_slot.duration) // 60, (daily_start + session.time_slot.duration) % 60)
        return mutated

    def _repair_schedule(self, schedule: List[Schedule]) -> List[Schedule]:
        """إصلاح الجدول لحل التعارضات الأساسية"""
        # إصلاح تعارضات القاعات
        room_assignments = defaultdict(list)
        for session in schedule:
            room_assignments[session.room_id].append(session)
        
        for room_id, sessions in room_assignments.items():
            sessions.sort(key=lambda s: s.time_slot.start_minutes)
            for i in range(1, len(sessions)):
                prev = sessions[i-1]
                curr = sessions[i]
                if prev.time_slot.overlaps(curr.time_slot):
                    # تأخير الجلسة المتعارضة
                    new_start = prev.time_slot.end_minutes + self.config.min_break_between_classes
                    curr.time_slot.start_minutes = new_start
                    curr.time_slot.end_minutes = new_start + curr.time_slot.duration
        
        return schedule

    def _create_next_generation(self, island_idx: int) -> List[List[Schedule]]:
        """إنشاء الجيل التالي لجزيرة محددة"""
        island = self.islands[island_idx]
        new_population = []
        
        # النخبة: أفضل الجداول تنتقل مباشرة
        elites = sorted(island, key=self._fitness, reverse=True)[:self.elitism_count]
        new_population.extend(elites)
        
        # التكاثر: حتى نملأ حجم الجزيرة
        while len(new_population) < len(island):
            parent1, parent2 = self._select_parents(island)
            child = self._crossover(parent1, parent2)
            child = self._mutate(child)
            child = self._repair_schedule(child)
            new_population.append(child)
        
        return new_population[:len(island)]

    def _migrate_between_islands(self):
        """الهجرة بين الجزر لنقل الحلول الجيدة"""
        migrants = []
        for island in self.islands:
            num_migrants = max(1, int(self.migration_rate * len(island)))
            migrants.append(sorted(island, key=self._fitness, reverse=True)[:num_migrants])
        
        # تبادل المهاجرين بين الجزر
        for i in range(self.island_count):
            source_idx = (i + 1) % self.island_count
            self.islands[i].extend(migrants[source_idx])
            self.islands[i] = self.islands[i][:len(self.islands[0])]

    def calculate_diversity(self) -> float:
        """حساب تنوع السكان"""
        fitness_values = [self._fitness(schedule) for island in self.islands for schedule in island]
        if len(fitness_values) < 2:
            return 0.0
        return statistics.stdev(fitness_values)

    def evolve(self) -> Tuple[List[Schedule], Dict[str, Any]]:
        """تشغيل عملية التطور"""
        best_fitness = 0.0
        best_schedule = None
        stagnation_count = 0
        stats = {
            "best_fitness_history": [],
            "diversity_history": [],
            "generation_times": []
        }
        
        for gen in range(self.generations):
            gen_start = systime.time()
            
            # تحديث كل جزيرة
            for i in range(self.island_count):
                self.islands[i] = self._create_next_generation(i)
            
            # الهجرة بين الجزر كل 5 أجيال
            if gen % 5 == 0:
                self._migrate_between_islands()
            
            # حساب أفضل لياقة في هذا الجيل
            current_best_fitness = 0.0
            for island in self.islands:
                for schedule in island:
                    fitness = self._fitness(schedule)
                    if fitness > current_best_fitness:
                        current_best_fitness = fitness
                        if fitness > best_fitness:
                            best_fitness = fitness
                            best_schedule = schedule
            
            # حساب التنوع
            diversity = self.calculate_diversity()
            
            # تحديث الإحصائيات
            stats["best_fitness_history"].append(current_best_fitness)
            stats["diversity_history"].append(diversity)
            stats["generation_times"].append(systime.time() - gen_start)
            
            # التحقق من الركود
            if current_best_fitness <= best_fitness:
                stagnation_count += 1
                if stagnation_count > 10:
                    logger.info(f"التوقف المبكر بسبب الركود في الجيل {gen}")
                    break
            else:
                stagnation_count = 0
            
            logger.info(f"الجيل {gen+1}/{self.generations}: اللياقة = {current_best_fitness:.4f}, التنوع = {diversity:.4f}")
        
        # تحسين نهائي لأفضل جدول
        optimized_schedule = self._final_optimization(best_schedule)
        return optimized_schedule, stats

    def _final_optimization(self, schedule: List[Schedule]) -> List[Schedule]:
        """تحسين نهائي محلي لأفضل جدول"""
        # تحسين الفجوات الزمنية
        optimized = self._optimize_time_gaps(schedule)
        # تحسين استخدام القاعات
        optimized = self._optimize_room_usage(optimized)
        return optimized

    def _optimize_time_gaps(self, schedule: List[Schedule]) -> List[Schedule]:
        """تقليل الفجوات الزمنية بين محاضرات المجموعات"""
        group_sessions = defaultdict(list)
        for session in schedule:
            group_sessions[session.group_id].append(session)
        
        for group_id, sessions in group_sessions.items():
            sessions.sort(key=lambda s: s.time_slot.start_minutes)
            for i in range(1, len(sessions)):
                prev = sessions[i-1]
                curr = sessions[i]
                
                if prev.time_slot.day != curr.time_slot.day:
                    continue
                
                gap = curr.time_slot.start_minutes - prev.time_slot.end_minutes
                if gap > 30:  # دقائق
                    # تقليل الفجوة إذا كان الوقت متاحًا
                    new_start = prev.time_slot.end_minutes + self.config.min_break_between_classes
                    if self._is_time_slot_available(curr, new_start, schedule):
                        curr.time_slot.start_minutes = new_start
                        curr.time_slot.end_minutes = new_start + curr.time_slot.duration
        
        return schedule

    def _optimize_room_usage(self, schedule: List[Schedule]) -> List[Schedule]:
        """تحسين استخدام القاعات لتقليل التغيير بين المحاضرات"""
        # ... (تنفيذ متقدم لتحسين استخدام القاعات)
        return schedule

    def _is_time_slot_available(self, session: Schedule, new_start: int, full_schedule: List[Schedule]) -> bool:
        """التحقق من توفر الوقت الجديد مع الالتزام بالأيام المسموحة فقط"""
        new_end = new_start + session.time_slot.duration
        day = new_start // (24 * 60)
        allowed_days = [d.value if hasattr(d, 'value') else int(d) for d in self.config.working_days]
        if day not in allowed_days:
            return False
        for s in full_schedule:
            if s == session:
                continue
            # نفس المدرس
            s_day = s.time_slot.day.value if hasattr(s.time_slot.day, 'value') else int(s.time_slot.day)
            if s.instructor_id == session.instructor_id:
                if s_day == day:
                    if s.time_slot.overlaps(TimeSlot(
                        day=day,
                        start_time=time(new_start % (24*60) // 60, new_start % 60),
                        end_time=time(new_end % (24*60) // 60, new_end % 60)
                    )):
                        return False
            # نفس المجموعة
            if s.group_id == session.group_id:
                if s_day == day:
                    if s.time_slot.overlaps(TimeSlot(
                        day=day,
                        start_time=time(new_start % (24*60) // 60, new_start % 60),
                        end_time=time(new_end % (24*60) // 60, new_end % 60)
                    )):
                        return False
        return True