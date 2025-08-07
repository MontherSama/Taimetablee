import streamlit as st
import json
from model import Config
from utils.config_manager import ConfigManager
from utils.error_handler import ErrorHandler

# تهيئة session_state الأساسية
if "current_step" not in st.session_state:
    st.session_state.current_step = 1
if "selected_data" not in st.session_state:
    st.session_state.selected_data = None
if "data_source" not in st.session_state:
    st.session_state.data_source = None
if "schedule" not in st.session_state:
    st.session_state.schedule = None
config_manager = ConfigManager()
config = config_manager.get_config()

def save_config(config):
    # يمكنك هنا حفظ الإعدادات إلى ملف أو قاعدة بيانات حسب الحاجة
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def main():
    st.title("⚙️ الإعدادات المتقدمة")
    # استخدم session_state لتخزين الإعدادات
    if "config" not in st.session_state:
        # تحميل الإعدادات الافتراضية أو من ملف
        st.session_state.config = Config
    config = st.session_state.config
    unsaved_changes = st.session_state.get('unsaved_changes_config', False)
    show_modal = st.session_state.get('show_confirm_modal_config', False)

    def set_unsaved(val=True):
        st.session_state.unsaved_changes_config = val

    st.subheader("إعدادات خوارزمية الجدولة")
    with st.expander("أوزان العقوبات"):
        col1, col2 = st.columns(2)
        with col1:
            val = st.slider(
                "تعارض القاعات", 1000, 30000, config["penalty_weights"]["room_conflict"], 1000,
                on_change=set_unsaved
            )
            if val != config["penalty_weights"]["room_conflict"]:
                set_unsaved()
            config["penalty_weights"]["room_conflict"] = val
            val = st.slider(
                "تعارض المدرسين", 1000, 30000, config["penalty_weights"]["instructor_conflict"], 1000,
                on_change=set_unsaved
            )
            if val != config["penalty_weights"]["instructor_conflict"]:
                set_unsaved()
            config["penalty_weights"]["instructor_conflict"] = val
            val = st.slider(
                "تعارض المجموعات", 1000, 30000, config["penalty_weights"]["group_conflict"], 1000,
                on_change=set_unsaved
            )
            if val != config["penalty_weights"]["group_conflict"]:
                set_unsaved()
            config["penalty_weights"]["group_conflict"] = val
        with col2:
            val = st.slider(
                "عدم توافق المرافق", 10, 500, config["penalty_weights"]["facility_mismatch"], 10,
                on_change=set_unsaved
            )
            if val != config["penalty_weights"]["facility_mismatch"]:
                set_unsaved()
            config["penalty_weights"]["facility_mismatch"] = val
            val = st.slider(
                "تفضيلات الوقت", 10, 500, config["penalty_weights"]["time_preference"], 10,
                on_change=set_unsaved
            )
            if val != config["penalty_weights"]["time_preference"]:
                set_unsaved()
            config["penalty_weights"]["time_preference"] = val

    with st.expander("معلمات الخوارزمية الجينية"):
        col1, col2 = st.columns(2)
        with col1:
            val = st.slider(
                "حجم السكان", 10, 200, config["ga_params"]["population_size"], 10,
                on_change=set_unsaved
            )
            if val != config["ga_params"]["population_size"]:
                set_unsaved()
            config["ga_params"]["population_size"] = val
            val = st.slider(
                "عدد الأجيال", 10, 200, config["ga_params"]["generations"], 10,
                on_change=set_unsaved
            )
            if val != config["ga_params"]["generations"]:
                set_unsaved()
            config["ga_params"]["generations"] = val
        with col2:
            val = st.slider(
                "معدل التقاطع", 0.0, 1.0, config["ga_params"]["crossover_rate"], 0.01,
                on_change=set_unsaved
            )
            if val != config["ga_params"]["crossover_rate"]:
                set_unsaved()
            config["ga_params"]["crossover_rate"] = val
            val = st.slider(
                "معدل الطفرة", 0.0, 1.0, config["ga_params"]["mutation_rate"], 0.01,
                on_change=set_unsaved
            )
            if val != config["ga_params"]["mutation_rate"]:
                set_unsaved()
            config["ga_params"]["mutation_rate"] = val

    with st.expander("إعدادات الوقت"):
        col1, col2 = st.columns(2)
        with col1:
            start_hour = st.slider("ساعة البدء", 0, 12, int(config["daily_start_time"].split(":")[0]), on_change=set_unsaved)
            start_minute = st.slider("دقيقة البدء", 0, 59, int(config["daily_start_time"].split(":")[1]), on_change=set_unsaved)
            if f"{start_hour:02d}:{start_minute:02d}" != config["daily_start_time"]:
                set_unsaved()
            config["daily_start_time"] = f"{start_hour:02d}:{start_minute:02d}"
        with col2:
            end_hour = st.slider("ساعة الانتهاء", 12, 23, int(config["daily_end_time"].split(":")[0]), on_change=set_unsaved)
            end_minute = st.slider("دقيقة الانتهاء", 0, 59, int(config["daily_end_time"].split(":")[1]), on_change=set_unsaved)
            if f"{end_hour:02d}:{end_minute:02d}" != config["daily_end_time"]:
                set_unsaved()
            config["daily_end_time"] = f"{end_hour:02d}:{end_minute:02d}"
        val = st.slider(
            "الحد الأدنى للاستراحة بين المحاضرات (دقائق)", 5, 60, config["min_break_between_classes"], 5,
            on_change=set_unsaved
        )
        if val != config["min_break_between_classes"]:
            set_unsaved()
        config["min_break_between_classes"] = val

    st.subheader("أيام العمل")
    days = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
    selected_days = st.multiselect(
        "اختر أيام العمل",
        days,
        default=[d for d in days if d in config["working_days"]],
        on_change=set_unsaved
    )
    if selected_days != config["working_days"]:
        set_unsaved()
    config["working_days"] = selected_days

    # زر الحفظ مع modal confirmation عند وجود تغييرات غير محفوظة
    # عند التحديث
    if st.button("💾 حفظ الإعدادات", type="primary"):
        try:
            config_manager.update_config(config)
            st.success("تم حفظ الإعدادات بنجاح!")
        except Exception as e:
            error_msg = ErrorHandler.handle_error(e, context="إعدادات النظام")
            st.error(error_msg)

    # Modal confirmation
    if show_modal:
        with st.modal("تأكيد الحفظ"):
            st.warning("لديك تغييرات غير محفوظة. هل تريد حفظها؟")
            colm1, colm2 = st.columns(2)
            with colm1:
                if st.button("نعم، احفظ", key="confirm_save_config"):
                    save_config(config)
                    st.session_state.config = config
                    st.session_state.show_confirm_modal_config = False
                    st.session_state.unsaved_changes_config = False
                    st.success("تم حفظ الإعدادات بنجاح!")
                    st.rerun()
            with colm2:
                if st.button("إلغاء", key="cancel_save_config"):
                    st.session_state.show_confirm_modal_config = False
                    st.rerun()

    st.divider()
    st.subheader("استعادة الإعدادات")
    if st.button("🔄 استعادة الإعدادات الافتراضية"):
        default_config = {
            "penalty_weights": {
                "room_conflict": 10000,
                "instructor_conflict": 20000,
                "group_conflict": 15000,
                "facility_mismatch": 50,
                "time_preference": 30
            },
            "ga_params": {
                "population_size": 100,
                "generations": 50,
                "crossover_rate": 0.8,
                "mutation_rate": 0.1,
                "elitism_count": 5
            },
            "daily_start_time": "08:00",
            "daily_end_time": "16:00",
            "min_break_between_classes": 15,
            "working_days": ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        }
        save_config(default_config)
        st.session_state.config = default_config
        st.success("تم استعادة الإعدادات الافتراضية بنجاح!")
        st.rerun()

if __name__ == "__main__":
    main()