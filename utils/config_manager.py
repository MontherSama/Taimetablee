import json
import os
from copy import deepcopy
from model import Config

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """تحميل الإعدادات من ملف أو إنشاء إعدادات افتراضية"""
        self.config_file = "config.json"
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = Config(**data)
            except Exception as e:
                print(f"خطأ في تحميل الإعدادات: {e}")
                self.config = Config()
        else:
            self.config = Config()
    
    def get_config(self):
        """الحصول على نسخة من كائن الإعدادات"""
        return deepcopy(self.config)
    
    def update_config(self, new_config):
        """تحديث الإعدادات وحفظها"""
        self.config = new_config
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(new_config.__dict__, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"خطأ في حفظ الإعدادات: {e}")
            return False
