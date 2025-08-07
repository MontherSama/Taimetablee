import streamlit as st
import json
from utils.util import save_config
from model import Config
from utils.config_manager import ConfigManager
from utils.error_handler import ErrorHandler

def main():
    st.title("⚙️ الإعدادات المتقدمة")
    
    config_manager = ConfigManager()
    # استخدم session_state لتخزين الإعدادات
    if "config" not in st.session_state:
        # تحميل الإعدادات الافتراضية أو من ملف
        st.session_state.config = Config()
    
    config = config_manager.get_config()
    unsaved_changes = st.session_state.get('unsaved_changes_config', False)
    show_modal = st.session_state.get('show_confirm_modal_config', False)

    def set_unsaved(val=True):
        st.session_state.unsaved_changes_config = val

    st.subheader("إعدادات خوارزمية الجدولة")
    with st.expander("أوزان العقوبات"):
        col1, col2 = st.columns(2)
        with col1:
            val = st.slider(
                "تعارض القاعات", 1000, 30000, config.penalty_weights.get("room_conflict", 10000), 1000,
                on_change=set_unsaved
            )
            if val != config.penalty_weights.get("room_conflict", 10000):
                set_unsaved()
            config.penalty_weights["room_conflict"] = val
            
            val = st.slider(
                "تعارض المدرسين", 1000, 30000, config.penalty_weights.get("instructor_conflict", 20000), 1000,
                on_change=set_unsaved
            )
            if val != config.penalty_weights.get("instructor_conflict", 20000):
                set_unsaved()
            config.penalty_weights["instructor_conflict"] = val
            
            val = st.slider(
                "تعارض المجموعات", 1000, 30000, config.penalty_weights.get("group_conflict", 15000), 1000,
                on_change=set_unsaved
            )
            if val != config.penalty_weights.get("group_conflict", 15000):
                set_unsaved()
            config.penalty_weights["group_conflict"] = val
        
        with col2:
            val = st.slider(
                "عدم توافق المرافق", 10, 500, config.penalty_weights.get("facility_mismatch", 50), 10,
                on_change=set_unsaved
            )
            if val != config.penalty_weights.get("facility_mismatch", 50):
                set_unsaved()
            config.penalty_weights["facility_mismatch"] = val
            
            val = st.slider(
                "تفضيلات الوقت", 10, 500, config.penalty_weights.get("time_preference", 30), 10,
                on_change=set_unsaved
            )
            if val != config.penalty_weights.get("time_preference", 30):
                set_unsaved()
            config.penalty_weights["time_preference"] = val

    with st.expander("معلمات الخوارزمية الجينية"):
        col1, col2 = st.columns(2)
        with col1:
            val = st.slider(
                "حجم السكان", 10, 200, config.ga_params.get("population_size", 100), 10,
                on_change=set_unsaved
            )
            if val != config.ga_params.get("population_size", 100):
                set_unsaved()
            config.ga_params["population_size"] = val
            
            val = st.slider(
                "عدد الأجيال", 10, 200, config.ga_params.get("generations", 50), 10,
                on_change=set_unsaved
            )
            if val != config.ga_params.get("generations", 50):
                set_unsaved()
            config.ga_params["generations"] = val
        
        with col2:
            val = st.slider(
                "معدل التقاطع", 0.0, 1.0, config.ga_params.get("crossover_rate", 0.8), 0.01,
                on_change=set_unsaved
            )
            if val != config.ga_params.get("crossover_rate", 0.8):
                set_unsaved()
            config.ga_params["crossover_rate"] = val
            
            val = st.slider(
                "معدل الطفرة", 0.0, 1.0, config.ga_params.get("mutation_rate", 0.1), 0.01,
                on_change=set_unsaved
            )
            if val != config.ga_params.get("mutation_rate", 0.1):
                set_unsaved()
            config.ga_params["mutation_rate"] = val

    with st.expander("إعدادات الوقت"):
        col1, col2 = st.columns(2)
        with col1:
            start_hour = st.slider("ساعة البدء", 0, 12, 8, on_change=set_unsaved)
            start_minute = st.slider("دقيقة البدء", 0, 59, 0, on_change=set_unsaved)
            config.daily_start_time = f"{start_hour:02d}:{start_minute:02d}"
        
        with col2:
            end_hour = st.slider("ساعة الانتهاء", 12, 23, 16, on_change=set_unsaved)
            end_minute = st.slider("دقيقة الانتهاء", 0, 59, 0, on_change=set_unsaved)
            config.daily_end_time = f"{end_hour:02d}:{end_minute:02d}"
        
        val = st.slider(
            "الحد الأدنى للاستراحة بين المحاضرات (دقائق)", 5, 60, config.min_break_between_classes, 5,
            on_change=set_unsaved
        )
        if val != config.min_break_between_classes:
            set_unsaved()
        config.min_break_between_classes = val

    st.subheader("أيام العمل")
    days = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
    selected_days = st.multiselect(
        "اختر أيام العمل",
        days,
        default=[d for d in days if d in config.working_days],
        on_change=set_unsaved
    )
    if selected_days != config.working_days:
        set_unsaved()
    config.working_days = selected_days

    # عند التحديث
    if st.button("💾 حفظ الإعدادات", type="primary"):
        try:
            config_manager.update_config(config)
            st.success("تم حفظ الإعدادات بنجاح!")
        except Exception as e:
            error_msg = ErrorHandler.handle_error(e, context="الإعدادات المتقدمة")
            st.error(error_msg)

    st.divider()
    st.subheader("استعادة الإعدادات")
    if st.button("🔄 استعادة الإعدادات الافتراضية"):
        default_config = Config()
        save_config(default_config)
        st.session_state.config = default_config
        st.success("تم استعادة الإعدادات الافتراضية بنجاح!")
        st.rerun()
    
    # زر العودة
    st.markdown("---")
    if st.button("⬅️ العودة للواجهة الرئيسية", use_container_width=True):
        st.session_state.show_advanced_settings = False
        st.switch_page("streamlit_app.py")

if __name__ == "__main__":
    main()