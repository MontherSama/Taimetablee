import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from copy import deepcopy
import uuid
from utils.util import validate_room_data, validate_instructor_data, validate_group_data, validate_course_data
from utils.error_handler import ErrorHandler
from utils.change_tracker import ChangeTracker
tracker = ChangeTracker()

# ------ ثوابت التصميم ------
PRIMARY_COLOR = "#1e88e5"
SECONDARY_COLOR = "#0d47a1"
ACCENT_COLOR = "#ff9800"
BACKGROUND_COLOR = "#f5f9ff"
TEXT_COLOR = "#333333"
FONT_FAMILY = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"

# ------ تحميل التصميم المخصص ------
def load_custom_css():
    st.markdown(f"""
    <style>
    :root {{
        --primary: {PRIMARY_COLOR};
        --secondary: {SECONDARY_COLOR};
        --accent: {ACCENT_COLOR};
        --background: {BACKGROUND_COLOR};
        --text: {TEXT_COLOR};
        --font: {FONT_FAMILY};
    }}
    
    * {{
        font-family: var(--font);
    }}
    
    body {{
        background: linear-gradient(135deg, #f5f9ff 0%, #e3f2fd 100%);
        color: var(--text);
    }}
    
    .stApp {{
        background: transparent;
    }}
    
    .header {{
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
        padding: 1.5rem 1rem;
        border-radius: 0 0 20px 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        color: white;
        margin-bottom: 2rem;
    }}
    
    .header h1 {{
        font-size: 2rem;
        font-weight: 700;
    }}
    
    .card {{
        background: white;
        border-radius: 15px;
        box-shadow: 0 6px 15px rgba(0,0,0,0.08);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }}
    
    .tab-container {{
        display: flex;
        gap: 10px;
        margin-bottom: 1.5rem;
    }}
    
    .tab-button {{
        flex: 1;
        padding: 12px;
        background: #f0f7ff;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        text-align: center;
    }}
    
    .tab-button:hover {{
        background: #e3f2fd;
        transform: translateY(-2px);
    }}
    
    .tab-button.active {{
        background: var(--primary);
        color: white;
        box-shadow: 0 4px 10px rgba(30, 136, 229, 0.3);
    }}
    
    .data-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
    }}
    
    .data-table th {{
        background: var(--primary);
        color: white;
        padding: 12px;
        text-align: left;
    }}
    
    .data-table td {{
        padding: 10px;
        border-bottom: 1px solid #eee;
    }}
    
    .data-table tr:nth-child(even) {{
        background: #f9fbfe;
    }}
    
    .data-table tr:hover {{
        background: #edf4ff;
    }}
    
    .action-button {{
        background: var(--primary);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 15px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.3s;
    }}
    
    .action-button:hover {{
        background: var(--secondary);
        transform: translateY(-2px);
    }}
    
    .form-card {{
        background: #f8fbff;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        border-left: 4px solid var(--primary);
    }}
    
    .form-row {{
        display: flex;
        gap: 15px;
        margin-bottom: 15px;
    }}
    
    .form-column {{
        flex: 1;
    }}
    
    .form-footer {{
        display: flex;
        gap: 10px;
        margin-top: 20px;
    }}
    </style>
    """, unsafe_allow_html=True)

def show_changes():
    if "original_data" in st.session_state and "selected_data" in st.session_state:
        original = st.session_state.original_data
        modified = st.session_state.selected_data
        
        changes = []
        
        # مقارنة القاعات
        orig_rooms = {r['id']: r for r in original.get('rooms', [])}
        mod_rooms = {r['id']: r for r in modified.get('rooms', [])}
        
        for id, room in mod_rooms.items():
            orig_room = orig_rooms.get(id, {})
            if orig_room != room:
                changes.append(f"تم تعديل القاعة: {room.get('name', id)}")
        
        # مقارنة المدرسين
        orig_inst = {i['id']: i for i in original.get('instructors', [])}
        mod_inst = {i['id']: i for i in modified.get('instructors', [])}
        for id, inst in mod_inst.items():
            orig_i = orig_inst.get(id, {})
            if orig_i != inst:
                changes.append(f"تم تعديل المدرس: {inst.get('name', id)}")
        
        # مقارنة المجموعات
        orig_groups = {g['id']: g for g in original.get('groups', [])}
        mod_groups = {g['id']: g for g in modified.get('groups', [])}
        for id, group in mod_groups.items():
            orig_g = orig_groups.get(id, {})
            if orig_g != group:
                changes.append(f"تم تعديل المجموعة: {group.get('major', id)}")
        
        # مقارنة المواد
        orig_courses = {c['id']: c for c in original.get('courses', [])}
        mod_courses = {c['id']: c for c in modified.get('courses', [])}
        for id, course in mod_courses.items():
            orig_c = orig_courses.get(id, {})
            if orig_c != course:
                changes.append(f"تم تعديل المادة: {course.get('name', id)}")
        
        if changes:
            with st.expander("🔄 التعديلات غير المحفوظة على الملف الأصلي"):
                for change in changes:
                    st.info(change)
        else:
            st.info("لا توجد تعديلات غير محفوظة على الملف الأصلي")

# ------ دوال مساعدة ------
def generate_unique_id(prefix=""):
    """إنشاء معرف فريد عشوائي"""
    return f"{prefix}_{str(uuid.uuid4())[:8]}"

def validate_room(room):
    """التحقق من صحة بيانات القاعة"""
    errors = []
    if not room.get('id'):
        errors.append("معرف القاعة مطلوب")
    if not room.get('name'):
        errors.append("اسم القاعة مطلوب")
    if not room.get('type'):
        errors.append("نوع القاعة مطلوب")
    if not room.get('capacity') or room['capacity'] <= 0:
        errors.append("سعة القاعة يجب أن تكون رقمًا موجبًا")
    return errors

def validate_instructor(instructor):
    """التحقق من صحة بيانات المدرس"""
    errors = []
    if not instructor.get('id'):
        errors.append("معرف المدرس مطلوب")
    if not instructor.get('name'):
        errors.append("اسم المدرس مطلوب")
    if not instructor.get('expertise'):
        errors.append("يجب تحديد تخصص واحد على الأقل")
    if not instructor.get('max_teaching_hours') or instructor['max_teaching_hours'] <= 0:
        errors.append("الحد الأقصى لساعات التدريس يجب أن يكون رقمًا موجبًا")
    return errors

def validate_group(group):
    """التحقق من صحة بيانات المجموعة"""
    errors = []
    if not group.get('id'):
        errors.append("معرف المجموعة مطلوب")
    if not group.get('major'):
        errors.append("تخصص المجموعة مطلوب")
    if not group.get('level') or group['level'] <= 0:
        errors.append("مستوى المجموعة يجب أن يكون رقمًا موجبًا")
    if not group.get('student_count') or group['student_count'] <= 0:
        errors.append("عدد الطلاب يجب أن يكون رقمًا موجبًا")
    return errors

def validate_course(course, data):
    """التحقق من صحة بيانات المادة"""
    errors = []
    if not course.get('id'):
        errors.append("معرف المادة مطلوب")
    if not course.get('name'):
        errors.append("اسم المادة مطلوب")
    if not course.get('duration') or course['duration'] <= 0:
        errors.append("مدة المادة يجب أن تكون رقمًا موجبًا")
    
    # التحقق من وجود المدرس
    instructor_ids = [i['id'] for i in data.get('instructors', [])]
    if course.get('instructor_id') and course['instructor_id'] not in instructor_ids:
        errors.append("المدرس المحدد غير موجود")
    
    # التحقق من وجود المجموعة
    group_ids = [g['id'] for g in data.get('groups', [])]
    if course.get('group_id') and course['group_id'] not in group_ids:
        errors.append("المجموعة المحددة غير موجودة")
    
    return errors

def show_data_summary(data):
    """عرض ملخص للبيانات"""
    rooms_count = len(data.get('rooms', []))
    instructors_count = len(data.get('instructors', []))
    groups_count = len(data.get('groups', []))
    courses_count = len(data.get('courses', []))
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        display: flex;
        justify-content: space-between;
    ">
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 1.5rem; font-weight: 700;">{rooms_count}</div>
            <div style="font-size: 0.9rem;">القاعات</div>
        </div>
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 1.5rem; font-weight: 700;">{instructors_count}</div>
            <div style="font-size: 0.9rem;">المدرسين</div>
        </div>
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 1.5rem; font-weight: 700;">{groups_count}</div>
            <div style="font-size: 0.9rem;">المجموعات</div>
        </div>
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 1.5rem; font-weight: 700;">{courses_count}</div>
            <div style="font-size: 0.9rem;">المواد</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def room_form(key_prefix="", initial_data=None):
    """نموذج إضافة/تعديل قاعة"""
    if initial_data is None:
        initial_data = {}
    
    with st.form(key=f"{key_prefix}_room_form", clear_on_submit=not initial_data):
        col1, col2 = st.columns(2)
        with col1:
            room_id = st.text_input("المعرف", value=initial_data.get('id', generate_unique_id('ROOM')), 
                                   key=f"{key_prefix}_room_id")
            room_name = st.text_input("الاسم", value=initial_data.get('name', ''), 
                                    key=f"{key_prefix}_room_name")
            room_type = st.selectbox("النوع", ["نظرية", "عملي"], 
                                    index=0 if initial_data.get('type') != "عملي" else 1,
                                    key=f"{key_prefix}_room_type")
        with col2:
            room_capacity = st.number_input("السعة", min_value=10, max_value=200, 
                                          value=initial_data.get('capacity', 30), 
                                          key=f"{key_prefix}_room_capacity")
            facilities = st.multiselect("المرافق", ["بروجكتر", "سبورة ذكية", "حواسيب", "شبكة", "مكيف", "إنترنت"],
                                      default=initial_data.get('facilities', []),
                                      key=f"{key_prefix}_facilities")
        
        submitted = st.form_submit_button("💾 حفظ القاعة")
        if submitted:
            new_room = {
                "id": room_id,
                "name": room_name,
                "type": room_type,
                "capacity": room_capacity,
                "facilities": facilities
            }
            errors = validate_room(new_room)
            if errors:
                for error in errors:
                    st.error(error)
                return None
            return new_room
    return None

# ------ واجهة مدير البيانات ------
def save_data_to_current_file(data):
    if st.session_state.get("data_source") == "file" and st.session_state.get("current_file"):
        with open(st.session_state.current_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        st.session_state.original_data = deepcopy(data)


def manage_entity(entity, data, required_fields, id_field="id", numeric_fields=None, entity_name="", validate_func=None, tracker_type=None):
    st.subheader(f"إدارة {entity_name}")
    session_key_edit = f"edit_{entity}"
    session_key_delete = f"delete_{entity}"
    if session_key_edit not in st.session_state:
        st.session_state[session_key_edit] = None
    if session_key_delete not in st.session_state:
        st.session_state[session_key_delete] = None
    # عرض الجدول
    st.dataframe(pd.DataFrame(data))
    if data:
        st.markdown("---")
        st.subheader("التعديل أو الحذف")
        idx_options = [f"{i+1} - {item[id_field]}" for i, item in enumerate(data)]
        selected_idx = st.selectbox(
            f"اختر {entity_name} لتعديله أو حذفه",
            options=range(len(data)),
            format_func=lambda x: idx_options[x] if idx_options else "لا توجد بيانات",
            key=f"select_{entity}"
        )
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(f"تعديل {entity_name} المحدد", key=f"edit_btn_{entity}"):
                st.session_state[session_key_edit] = selected_idx
                st.rerun()
        with col2:
            if st.button(f"حذف {entity_name} المحدد", key=f"delete_btn_{entity}"):
                st.session_state[session_key_delete] = selected_idx
                st.rerun()
        if st.session_state[session_key_edit] is not None:
            st.markdown("---")
            st.subheader(f"تعديل {entity_name}")
            row = data[st.session_state[session_key_edit]]
            with st.form(key=f"edit_form_{entity}"):
                edited_row = {}
                for field in required_fields:
                    current_value = row.get(field, "")
                    if numeric_fields and field in numeric_fields:
                        min_val = 1 if field == "capacity" else 0
                        edited_row[field] = st.number_input(
                            field,
                            value=int(current_value) if str(current_value).isdigit() else min_val,
                            min_value=min_val,
                            key=f"edit_{entity}_{field}"
                        )
                    else:
                        edited_row[field] = st.text_input(
                            field,
                            value=str(current_value),
                            key=f"edit_{entity}_{field}"
                        )
                col1, col2, col3 = st.columns([1,1,2])
                with col1:
                    save_edit = st.form_submit_button("حفظ التعديلات")
                with col2:
                    cancel_edit = st.form_submit_button("إلغاء")
                if save_edit:
                    errors = []
                    for field in required_fields:
                        if not str(edited_row[field]).strip():
                            errors.append(f"حقل '{field}' مطلوب")
                    if edited_row[id_field] != row[id_field]:
                        if any(item[id_field] == edited_row[id_field] for i, item in enumerate(data) if i != st.session_key_edit):
                            errors.append(f"المعرف '{edited_row[id_field]}' مستخدم مسبقاً")
                    if validate_func:
                        valid, message = validate_func(edited_row)
                        if not valid:
                            errors.append(message)
                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        data[st.session_state[session_key_edit]] = edited_row
                        st.session_state.selected_data[entity] = data
                        if tracker_type:
                            tracker.log_change("EDIT", tracker_type, edited_row)
                        save_data_to_current_file(st.session_state.selected_data)
                        st.success("تم تحديث البيانات بنجاح")
                        st.session_state[session_key_edit] = None
                        st.rerun()
                if cancel_edit:
                    st.session_state[session_key_edit] = None
                    st.info("تم إلغاء التعديل")
                    st.rerun()
        if st.session_state[session_key_delete] is not None:
            st.markdown("---")
            st.subheader("تأكيد الحذف")
            item = data[st.session_state[session_key_delete]]
            st.warning(f"هل أنت متأكد من حذف {entity_name} ({item[id_field]})؟ لا يمكن التراجع عن هذه العملية.")
            col1, col2 = st.columns([1,2])
            with col1:
                if st.button("نعم، احذف", key=f"confirm_delete_{entity}"):
                    if tracker_type:
                        tracker.log_change("DELETE", tracker_type, item)
                    del data[st.session_state[session_key_delete]]
                    st.session_state.selected_data[entity] = data
                    save_data_to_current_file(st.session_state.selected_data)
                    st.success("تم الحذف بنجاح")
                    st.session_state[session_key_delete] = None
                    st.rerun()
            with col2:
                if st.button("لا، إلغاء الحذف", key=f"cancel_delete_{entity}"):
                    st.session_state[session_key_delete] = None
                    st.info("تم إلغاء عملية الحذف")
                    st.rerun()
    # زر إضافة عنصر جديد
    add_key = f"show_add_form_{entity}"
    if add_key not in st.session_state:
        st.session_state[add_key] = False
    if st.button(f"➕ إضافة {entity_name}", key=f"add_btn_{entity}"):
        st.session_state[add_key] = not st.session_state[add_key]
    if st.session_state[add_key]:
        st.markdown("---")
        st.subheader(f"إضافة {entity_name} جديد")
        with st.form(key=f"add_form_{entity}"):
            new_row = {}
            for field in required_fields:
                if numeric_fields and field in numeric_fields:
                    min_val = 1 if field == "capacity" else 0
                    new_row[field] = st.number_input(
                        f"{field} (جديد)",
                        value=min_val,
                        min_value=min_val,
                        key=f"add_{entity}_{field}"
                    )
                else:
                    new_row[field] = st.text_input(
                        f"{field} (جديد)",
                        key=f"add_{entity}_{field}"
                    )
            col1, col2 = st.columns([1,1])
            with col1:
                save_add = st.form_submit_button(f"إضافة {entity_name}")
            with col2:
                cancel_add = st.form_submit_button("إلغاء")
            if save_add:
                errors = []
                for field in required_fields:
                    if not str(new_row[field]).strip():
                        errors.append(f"حقل '{field}' مطلوب")
                if any(item[id_field] == new_row[id_field] for item in data):
                    errors.append(f"المعرف '{new_row[id_field]}' مستخدم مسبقاً")
                if validate_func:
                    valid, message = validate_func(new_row)
                    if not valid:
                        errors.append(message)
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    data.append(new_row)
                    st.session_state.selected_data[entity] = data
                    if tracker_type:
                        tracker.log_change("ADD", tracker_type, new_row)
                    save_data_to_current_file(st.session_state.selected_data)
                    st.success(f"تمت إضافة {entity_name} جديد بنجاح")
                    st.session_state[add_key] = False
                    st.rerun()
            if cancel_add:
                st.session_state[add_key] = False
                st.info("تم إلغاء الإضافة")
                st.rerun()
    return data

def main():
    load_custom_css()
    st.markdown(f"""
    <div class="header">
        <h1>مدير البيانات - نظام جدولة المحاضرات</h1>
    </div>
    """, unsafe_allow_html=True)
    if "selected_data" not in st.session_state or st.session_state.selected_data is None:
        st.warning("الرجاء اختيار مصدر البيانات أولاً من الصفحة الرئيسية")
        if st.button("العودة للصفحة الرئيسية"):
            st.session_state.show_data_manager = False
            st.switch_page("streamlit_app.py")
        st.stop()
    data = st.session_state.selected_data
    if st.session_state.get("data_source") == "file":
        show_changes()
    tabs = ["القاعات", "المدرسين", "المجموعات", "المواد"]
    current_tab = st.session_state.get("current_tab", "القاعات")
    st.markdown('<div class="tab-container">', unsafe_allow_html=True)
    for tab in tabs:
        is_active = "active" if current_tab == tab else ""
        if st.button(tab, key=f"tab_{tab}"):
            st.session_state.current_tab = tab
            st.rerun()
        st.markdown(f'<div class="tab-button {is_active}">{tab}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if current_tab == "القاعات":
        manage_entity(
            entity="rooms",
            data=data["rooms"],
            required_fields=["id", "name", "type", "capacity", "facilities"],
            id_field="id",
            numeric_fields=["capacity"],
            entity_name="قاعة",
            validate_func=validate_room_data,
            tracker_type="ROOM"
        )
    elif current_tab == "المدرسين":
        manage_entity(
            entity="instructors",
            data=data["instructors"],
            required_fields=["id", "name", "expertise", "max_teaching_hours"],
            id_field="id",
            numeric_fields=["max_teaching_hours"],
            entity_name="مدرس",
            validate_func=validate_instructor_data,
            tracker_type="INSTRUCTOR"
        )
    elif current_tab == "المجموعات":
        manage_entity(
            entity="groups",
            data=data["groups"],
            required_fields=["id", "major", "level", "student_count"],
            id_field="id",
            numeric_fields=["level", "student_count"],
            entity_name="مجموعة",
            validate_func=validate_group_data,
            tracker_type="GROUP"
        )
    elif current_tab == "المواد":
        manage_entity(
            entity="courses",
            data=data["courses"],
            required_fields=["id", "name", "duration", "course_type", "instructor_id", "group_id"],
            id_field="id",
            numeric_fields=["duration"],
            entity_name="مادة",
            validate_func=validate_course_data,
            tracker_type="COURSE"
        )
    # ...existing code...
    # ------ أزرار التحكم ------
    st.markdown("---")
    
    # زر استعادة النسخة الأصلية (إذا كان مصدر البيانات ملف)
    if st.session_state.get("data_source") == "file":
        if st.button("🔄 استعادة النسخة الأصلية", type="secondary", use_container_width=True):
            st.session_state.selected_data = deepcopy(st.session_state.original_data)
            st.success("تم استعادة النسخة الأصلية من الملف!")
            st.rerun()
    
    col1, col2, col3 = st.columns([1,1,2])
    with col1:
        if st.button("💾 حفظ البيانات في الجلسة", use_container_width=True):
            st.session_state.selected_data = data
            st.success("تم حفظ البيانات في الجلسة بنجاح!")
    with col2:
        st.download_button(
            label="📥 تصدير البيانات",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name=f"timetable_data_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    with col3:
        uploaded_file = st.file_uploader("رفع ملف بيانات", type=["json"], label_visibility="collapsed")
        if uploaded_file is not None:
            try:
                loaded = json.load(uploaded_file)
                st.session_state.selected_data = loaded
                st.success("تم تحميل البيانات بنجاح!")
                st.rerun()
            except Exception as e:
                st.error(f"خطأ في تحميل الملف: {str(e)}")
    
    # زر الحفظ على الملف الأصلي
    if st.session_state.get("data_source") == "file":
        if st.button("💾 حفظ التعديلات على الملف الأصلي", type="primary", use_container_width=True):
            with open(st.session_state.current_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            st.session_state.original_data = deepcopy(data)
            st.success(f"تم حفظ التعديلات على الملف: {st.session_state.current_file}")
    
    # زر العودة والمتابعة
    st.markdown("---")
    col1, col2 = st.columns([1,2])
    with col1:
        if st.button("⬅️ العودة للمعاينة", use_container_width=True):
            st.session_state.show_data_manager = False
            st.rerun()
    with col2:
        if st.button("💾 حفظ البيانات والمتابعة", type="primary", use_container_width=True):
            st.session_state.selected_data = data
            st.session_state.show_data_manager = False
            st.session_state.current_step = 2
            st.switch_page("streamlit_app.py")

# ------ تشغيل التطبيق ------
if __name__ == "__main__":
    main()