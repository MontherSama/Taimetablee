
# تعريف كلاس المادة الدراسية مع دوال مساعدة بالعربية
from dataclasses import dataclass, field
from typing import List, Optional
from ast import Assign
import logging
import json
from dataclasses import dataclass, field
from datetime import time
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import time

# @dataclass
# class Course:
#     """
#     يمثل مقرر دراسي في النظام.
#     """
#     id: str
#     name: str
#     course_type: str
#     duration: int
#     required_facilities: List[str] = field(default_factory=list)
#     instructors: List['Instructor'] = field(default_factory=list)
#     groups: List['Group'] = field(default_factory=list)
#     sessions: List['Session'] = field(default_factory=list)

#     def add_instructor(self, instr: 'Instructor'):
#         """
#         إضافة مدرس إلى قائمة المدرسين لهذا المقرر.
#         """
#         if instr not in self.instructors:
#             self.instructors.append(instr)
#             # يمكن إضافة تسجيل في السجل هنا إذا رغبت

#     def create_sessions(self, types: List[str]):
#         """
#         إنشاء جلسات للمقرر حسب الأنواع المطلوبة.
#         """
#         for t in types:
#             self.sessions.append(Session(self, t, self.duration))


# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
# نموذج البيانات
class DayOfWeek(Enum):
    SATURDAY = 0
    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6

    @classmethod
    def from_int(cls, day_int: int) -> 'DayOfWeek':
        return cls(day_int)
    
    def to_arabic(self) -> str:
        names = {
            0: "السبت",
            1: "الأحد",
            2: "الاثنين",
            3: "الثلاثاء",
            4: "الأربعاء",
            5: "الخميس",
            6: "الجمعة"
        }
        return names[self.value]
@dataclass
class Config:
    rooms: List['Room'] = field(default_factory=list)
    instructors: List['Instructor'] = field(default_factory=list)
    groups: List['Group'] = field(default_factory=list)
    courses: List['Course'] = field(default_factory=list)
    working_days: List[DayOfWeek] = field(default_factory=lambda: [
        DayOfWeek.SUNDAY, DayOfWeek.MONDAY, DayOfWeek.TUESDAY,
        DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY
    ])
    daily_start_time: time = time(8, 0)
    daily_end_time: time = time(16, 0)
    min_break_between_classes: int = 15
    penalty_weights: Dict[str, float] = field(default_factory=lambda: {
        "facility": 50, "pref_day": 20, "pref_day_violation": 10,
        "pref_group": 30, "merge_bonus": 50, "merge_violation": 30,
        "short_break": 50, "minimize_gaps": 10, "balance_room_usage": 5,
        "instructor_preference": 5, "rotation_block": 20
    })
    population_size: int = 100
    ga_generations: int = 50
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    enable_repair: bool = True
    ga_params: Dict[str, Any] = field(default_factory=lambda: {
        "population_size": 100,
        "generations": 100,
        "crossover_rate": 0.85,
        "mutation_rate": 0.15,
        "elitism_count": 5,
        "penalty_weights": {
            "room_conflict": 10000,
            "instructor_conflict": 20000,
            "group_conflict": 15000,
            "facility_mismatch": 50,
            "time_preference": 30
        }
    })

    def __post_init__(self):
        # تعيين الأوزان الافتراضية إذا لم يتم توفيرها
        default_weights = {
            "room_conflict": 10000,
            "instructor_conflict": 20000,
            "group_conflict": 15000,
            "facility_mismatch": 50,
            "time_preference": 30
        }
        if "penalty_weights" not in self.ga_params:
            self.ga_params["penalty_weights"] = default_weights
        else:
            for key, value in default_weights.items():
                if key not in self.ga_params["penalty_weights"]:
                    self.ga_params["penalty_weights"][key] = value

    def get_working_days_ints(self) -> List[int]:
        return [day.value for day in self.working_days]


@dataclass(frozen=True)
class TimeSlot:
    day: int
    start_time: time
    end_time: time

    @property
    def start_minutes(self):
        return self.start_time.hour * 60 + self.start_time.minute

    @property
    def end_minutes(self):
        return self.end_time.hour * 60 + self.end_time.minute

    @property
    def duration(self):
        return self.end_minutes - self.start_minutes

    def overlaps(self, other: 'TimeSlot') -> bool:
        """
        تحقق إذا كان الفترتان الزمنيتان تتعارضان في نفس اليوم
        """
        if self.day != other.day:
            return False
        
        # التحقق من التعارض باستخدام الدقائق
        return not (self.end_minutes <= other.start_minutes or other.end_minutes <= self.start_minutes)
    
    def to_serializable(self):
        """إرجاع بيانات الفترة الزمنية بشكل dict قابل للتسلسل"""
        return {
            "day": self.day,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "duration": self.duration
        }

@dataclass
class Room:
    """
    Represents a classroom or lab environment.
    """
    id: str
    name: str
    type: str               # e.g., 'theoretical', 'lab', 'lecture_hall'
    capacity: int
    facilities: List[str]   # e.g., ['projector', 'computer']
    available_slots: Dict[int, List[TimeSlot]] = field(default_factory=dict)

    def generate_slots(self, config: Config):
        """
        Populate available_slots based on working days and lecture_block_minutes.
        """
        from datetime import datetime, timedelta
        self.available_slots.clear()
        for day in config.working_days:
            current = datetime.combine(datetime.today(), config.daily_start_time)
            end_time = datetime.combine(datetime.today(), config.daily_end_time)
            while current + timedelta(minutes=config.lecture_block_minutes) <= end_time:
                slot_end = current + timedelta(minutes=config.lecture_block_minutes)
                self.available_slots.setdefault(day, []).append(
                    TimeSlot(day=day, start_time=current.time(), end_time=slot_end.time())
                )
                current = slot_end
        logger.debug(f"Generated slots for Room {self.id}: {len(self.available_slots)} days")

@dataclass
class Group:
    """
    Represents a student group or class cohort.
    """
    id: str
    major: str
    level: int
    student_count: int
    enrolled_courses: List[str] = field(default_factory=list)
    schedule: List[TimeSlot] = field(default_factory=list)
    # parent_group_id: Optional[str]  # للفروع
    student_count: int
    subgroup_count: Optional[int] = None  # for large groups
    def set_subgroup_count(self, count: int):
        """
        Set the number of subgroups based on room capacity.
        """
        self.subgroup_count = count
        logger.debug(f"Group {self.id} set to {count} subgroups")

@dataclass
class Course:
    """
    Represents a course to be scheduled.
    """
    id: str
    name: str
    course_type: str                # 'theoretical' or 'lab'
    duration: int                   # in minutes
    instructor_id: str
    group_id: str
    required_facilities: List[str] = field(default_factory=list)
    expertise_required: str = "general"
    can_merge: bool = False
    merge_with: List[str] = field(default_factory=list)
    # Soft-constraint fields added for GA optimization
    preferred_times: List[TimeSlot] = field(default_factory=list)
    # Optional merge settings for large lecture halls
    can_merge: bool = False
    merge_with: List[str] = field(default_factory=list)
    # subgroup_count is computed dynamically based on room capacities (if needed)
    subgroup_count: Optional[int] = None

@dataclass
class Instructor:
    """
    Represents an instructor/teacher.
    """
    id: str
    name: str
    expertise: List[str]
    availability: List[TimeSlot] = field(default_factory=list)
    max_teaching_hours: int = 18
    # Soft preferences for GA
    preferred_days: List[int] = field(default_factory=list)
    preferred_groups: List[str] = field(default_factory=list)
    # Optional: preferred time slots for teaching
    available_slots: List[TimeSlot] = field(default_factory=list)
    preferred_slots: List[TimeSlot] = field(default_factory=list)  # دمج available_slots و preferred_days


    def set_availability(self, working_days: List[int], start: time, end: time):
        """
        Initialize availability slots for each working day.
        """
        self.availability = [TimeSlot(day=d, start_time=start, end_time=end) for d in working_days]
        logger.debug(f"Instructor {self.id} availability set for days {working_days}")
    def set_available_slots(self, working_days: List[int], start: time, end: time):
        """
        Initialize available slots for each working day.
        """
        self.available_slots = [TimeSlot(day=d, start_time=start, end_time=end) for d in working_days]
        logger.debug(f"Instructor {self.id} available slots set for days {working_days}")



@dataclass
class Schedule:
    """
    Represents a scheduled lecture assignment.
    """
    course_id: str
    room_id: str
    instructor_id: str
    time_slot: TimeSlot
    group_id: str
    assigned_course: Course
    assigned_room: Room
    assigned_instructor: Instructor
    assigned_group: Group
    status: str = "pending"
    penalty_score: int = 0

    def to_dict(self) -> Dict:
        return {
            "course": self.course_id,
            "room": self.room_id,
            "instructor": self.instructor_id,
            "day": self.time_slot.day,
            "start": self.time_slot.start_time.strftime("%H:%M"),
            "end": self.time_slot.end_time.strftime("%H:%M"),
            "status": self.status,
            "penalty": self.penalty_score
        }


@dataclass
class Session:
    course: 'Course'
    session_type: str
    duration: int
    assigned_instructor: Optional['Instructor'] = None
    assigned_group: Optional['Group'] = None
    assigned_timeslot: Optional['TimeSlot'] = None
    assigned_room: Optional['Room'] = None

@dataclass
class ScheduledClass:
    session: Session
    instructor: 'Instructor'
    group: 'Group'
    room: 'Room'
    timeslot: 'TimeSlot'
    status: str = "pending"
    penalty_score: int = 0

    def to_dict(self) -> dict:
        return {
            "course": self.session.course.id,
            "session_type": self.session.session_type,
            "instructor": self.instructor.id,
            "group": self.group.id,
            "room": self.room.id,
            "day": self.timeslot.day if hasattr(self.timeslot, 'day') else None,
            "start": self.timeslot.start_time.strftime("%H:%M"),
            "end": self.timeslot.end_time.strftime("%H:%M"),
            "status": self.status,
            "penalty": self.penalty_score
        }

@dataclass
class GAConfig:
    population_size: int = 100
    generations: int = 50
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    elitism_count: int = 5
    penalty_weights: Dict[str, float] = field(default_factory=lambda: {
        "room_conflict": 10000,
        "instructor_conflict": 20000,
        "group_conflict": 15000,
        "facility_mismatch": 50,
        "time_preference": 30
    })





# دوال تحويل dict إلى كائنات الداتا كلاس
@staticmethod
def room_from_dict(d):
    return Room(
        id=d["id"],
        name=d.get("name", ""),
        type=d.get("type", ""),
        capacity=d.get("capacity", 0),
        facilities=d.get("facilities", []) if isinstance(d.get("facilities", []), list) else str(d.get("facilities", "")).split(",")
    )

@staticmethod
def instructor_from_dict(d):
    return Instructor(
        id=d["id"],
        name=d.get("name", ""),
        expertise=d.get("expertise", []) if isinstance(d.get("expertise", []), list) else str(d.get("expertise", "")).split(",")
    )

@staticmethod
def group_from_dict(d):
    return Group(
        id=d["id"],
        major=d.get("major", ""),
        level=d.get("level", 0) if isinstance(d.get("level", 0), int) else d.get("level", ""),
        student_count=d.get("student_count", 0)
    )

@staticmethod
def course_from_dict(d):
    return Course(
        id=d["id"],
        name=d.get("name", ""),
        group_id=d.get("group_id", ""),
        instructor_id=d.get("instructor_id", ""),
        duration=d.get("duration", 1),
        course_type=d.get("course_type", ""),
        required_facilities=d.get("required_facilities", []) if isinstance(d.get("required_facilities", []), list) else str(d.get("required_facilities", "")).split(",")
    )

# class ResourceManager:
#     def reserve(self, resource_type: str, resource_id: str, slot: TimeSlot):
#         """حجز مورد (قاعة/مدرس) لفترة محددة"""
#         if self.is_available(resource_type, resource_id, slot):
#             # قم بحجز المورد
#             logger.info(f"Reserved {resource_type} {resource_id} for {slot}")
#         else:
#             logger.warning(f"Failed to reserve {resource_type} {resource_id} for {slot}")

#     def is_available(self, resource_type: str, resource_id: str, slot: TimeSlot) -> bool:
#         """التحقق من التوافر دون تعديل الحالة"""
#         # تحقق من التوافر بناءً على نوع المورد ومعرفه
#         if resource_type == "room":
#             return self._is_room_available(resource_id, slot)
#         elif resource_type == "instructor":
#             return self._is_instructor_available(resource_id, slot)
#         return False

#     def _is_room_available(self, room_id: str, slot: TimeSlot) -> bool:
#         """التحقق من توافر القاعة"""
#         # تحقق من توافر القاعة في الجدول الزمني
#         return True

#     def _is_instructor_available(self, instructor_id: str, slot: TimeSlot) -> bool:
#         """التحقق من توافر المدرس"""
#         # تحقق من توافر المدرس في الجدول الزمني
#         return True

# class EnhancedGeneticOptimizer:
#     # ... other methods ...

#     def _check_convergence(self, gen: int, fitness: float, diversity: float) -> bool:
#         # لا تتوقف مبكراً في الأجيال الأولى
#         if gen < 20:
#             return False
        
#         # 1. تقارب اللياقة
#         if gen > 30 and abs(fitness - self.best_fitness_history[-1]) < 0.001:
#             return True
        
#         # 2. تنوع منخفض جداً
#         if diversity < 0.05:
#             return True
        
#         # 3. عدم تحسن لمدة 20 جيلاً
#         if gen > 40 and fitness <= max(self.best_fitness_history[:-20]):
#             return True
        
#         return False
    

# class DataCache:
#     # _instance = None
#     # rooms = None
#     # instructors = None
#     # groups = None
#     # courses = None
    
#     # def __new__(cls):
#     #     if cls._instance is None:
#     #         cls._instance = super().__new__(cls)
#     #         cls._load_data()
#     #     return cls._instance
    
#     # @classmethod
#     # def _load_data(cls):
#     #     try:
#     #         with open("current_data.json", "r") as f:
#     #             data = json.load(f)
#     #             cls.rooms = [Room(**r) for r in data['rooms']]
#     #             cls.instructors = [Instructor(**i) for i in data['instructors']]
#     #             cls.groups = [Group(**g) for g in data['groups']]
#     #             cls.courses = [Course(**c) for c in data['courses']]
#     #     except Exception as e:
#     #         logger.error(f"Failed to load data: {str(e)}")
    
#     # @classmethod
#     # def get_rooms(cls):
#     #     return cls.rooms or []
    
#     # @classmethod
#     # def get_instructors(cls):
#     #     return cls.instructors or []
    
#     # @classmethod
#     # def get_groups(cls):
#     #     return cls.groups or []
    
#     # @classmethod
#     # def get_courses(cls):
#     #     return cls.courses or []