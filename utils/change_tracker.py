import logging
import json
from datetime import datetime

class ChangeTracker:
    def __init__(self):
        self.changes = []
        self.log_file = "utils/changes_log.json"
        self._load_log()
    
    def _load_log(self):
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                self.changes = json.load(f)
        except Exception:
            self.changes = []
    
    def log_change(self, action, target, details):
        """تسجيل تغيير جديد"""
        change = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "target": target,
            "details": details,
            "user": "admin"  # يمكن استبدالها بمعلومات المستخدم
        }
        self.changes.append(change)
        self._save_log()
    
    def _save_log(self):
        """حفظ سجل التغييرات في ملف"""
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.changes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"خطأ في حفظ سجل التغييرات: {e}")
    
    def get_recent_changes(self, count=10):
        """الحصول على أحدث التغييرات"""
        return self.changes[-count:]
