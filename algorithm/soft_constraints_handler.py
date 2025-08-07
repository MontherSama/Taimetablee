import logging
import random
import math
from copy import deepcopy
import time as systime

from model import Schedule, TimeSlot
from algorithm.soft_constraints_validator import SoftConstraintsValidator

# إعدادات تسجيل الدخول
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)



class SoftConstraintsOptimizer:
    """
    محرك تحسين الجدول عبر التعامل مع القيود المرنة.
    يستخدم simulated annealing لتحسين الجدول الناتج من CP‑SAT.
    """

    def __init__(self, schedules: list[Schedule], config):
        """
        schedules: قائمة الجداول المبدئية (Schedule objects).
        config: يحتوي على أوزان العقوبات للقيود المرنة وخيارات SA.
        """
        self.best = deepcopy(schedules)
        self.current = deepcopy(schedules)
        self.config = config
        self.temperature = config.sa_start_temp
        self.cooling_rate = config.sa_cooling_rate
    # في أعلى genetic_optimizer.py

    def _compute_cost(self, schedules: list[Schedule]) -> float:
        """
        يجمع تكلفة جميع القيود المرنة حسب Validator وأوزانها.
        """
        """
        يحسب التكلفة (penalty) للجدول بالكامل (قائمة الجداول) دفعة واحدة.
        """
        return SoftConstraintsValidator.penalty(
            schedules,
            self.config
        )
        # حساب التكلفة الإجمالية للجدول
        # total_penalty = 0.0
        # for sched in schedules:
        #     total_penalty += SoftConstraintsValidator.penalty(sched, self.config)
        # return total_penalty

    def _neighbor(self, schedules: list[Schedule]) -> list[Schedule]:
        """
        يولّد جدولاً مجاورًا عبر تبديل قاعتين أو يومين/وقتَين لمادتين.
        """
        neighbor = deepcopy(schedules)
        a, b = random.sample(range(len(neighbor)), 2)
        # نبدل موقعي الحصتين (time_slot) أو القاعات
        if random.random() < 0.5:
            neighbor[a].time_slot, neighbor[b].time_slot = neighbor[b].time_slot, neighbor[a].time_slot
        else:
            neighbor[a].assigned_room, neighbor[b].assigned_room = neighbor[b].assigned_room, neighbor[a].assigned_room
        return neighbor

    def optimize(self, max_iters: int = 10000):
        """
        يشغّل simulated annealing لتحسين الجدول.
        """
        try:
            current_cost = self._compute_cost(self.current)
            best_cost = current_cost
            logger.info(f"💡 بدء التحسين: التكلفة الحالية = {current_cost:.2f}")

            for it in range(max_iters):
                candidate = self._neighbor(self.current)
                cand_cost = self._compute_cost(candidate)
                delta = cand_cost - current_cost

                # قبول الحل
                if delta < 0 or random.random() < math.exp(-delta / self.temperature):
                    self.current = candidate
                    current_cost = cand_cost
                    if cand_cost < best_cost:
                        self.best = deepcopy(candidate)
                        best_cost = cand_cost
                        logger.debug(f"🆕 حل أفضل بإجمالي تكلفة {best_cost:.2f} عند التكرار {it}")

                # تبريد
                self.temperature *= self.cooling_rate
                if self.temperature < 1e-3:
                    break

            logger.info(f"🏁 انتهاء التحسين: أفضل تكلفة = {best_cost:.2f}")
            return self.best
        except Exception as e:
            logger.error(f"❌ خطأ أثناء تحسين الجدول (SA): {e}", exc_info=True)
            return self.best

