import streamlit as st
from streamlit.components.v1 import html
import json
from utils.util import load_sample_data, load_data_from_file, validate_json_structure, validate_room_data, validate_instructor_data, validate_group_data, validate_course_data
from utils.config_manager import ConfigManager
from utils.error_handler import ErrorHandler
from model import Config
from pages.data_manager import main as data_manager_main
from pages.advanced_settings import main as advanced_settings_main
from pages.timetable_viewer import main as timetable_viewer_main
from algorithm.cp_algorithm import CPSatScheduler
from algorithm.genetic_optimizer import EnhancedGeneticOptimizer
import pandas as pd
from copy import deepcopy

# تهيئة حالة الجلسة
if "current_step" not in st.session_state:
    st.session_state.current_step = 1

if "selected_data" not in st.session_state:
    st.session_state.selected_data = None

if "data_source" not in st.session_state:
    st.session_state.data_source = None

if "schedule" not in st.session_state:
    st.session_state.schedule = None

if "config" not in st.session_state:
    st.session_state.config = Config()

config_manager = ConfigManager()

# ------ CSS مخصص ------
def load_custom_css():
    st.markdown(f"""
    <style>
    :root {{
        --primary: #1e88e5;
        --secondary: #0d47a1;
        --accent: #ff9800;
        --background: #f5f9ff;
        --text: #333333;
        --font: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
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
        padding: 2rem 1rem;
        border-radius: 0 0 20px 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }}
    .header h1 {{
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }}
    .header p {{
        font-size: 1.2rem;
        opacity: 0.9;
        max-width: 800px;
        margin: 0 auto;
    }}
    .card {{
        background: white;
        border-radius: 15px;
        box-shadow: 0 6px 15px rgba(0,0,0,0.08);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
        border-left: 4px solid var(--primary);
    }}
    .card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 25px rgba(0,0,0,0.15);
    }}
    .card-title {{
        display: flex;
        align-items: center;
        gap: 12px;
        color: var(--secondary);
        margin-bottom: 1rem;
    }}
    .card-title i {{
        font-size: 1.8rem;
    }}
    .step-container {{
        display: flex;
        justify-content: space-between;
        margin: 2rem 0;
        position: relative;
    }}
    .step {{
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
        position: relative;
        z-index: 2;
    }}
    .step-number {{
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: var(--primary);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1.5rem;
        margin-bottom: 10px;
        box-shadow: 0 4px 10px rgba(30, 136, 229, 0.3);
    }}
    .step-active .step-number {{
        background: var(--secondary);
        transform: scale(1.1);
        animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
        0% {{ box-shadow: 0 0 0 0 rgba(13, 71, 161, 0.4); }}
        70% {{ box-shadow: 0 0 0 15px rgba(13, 71, 161, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(13, 71, 161, 0); }}
    }}
    .step-title {{
        font-weight: 600;
        text-align: center;
        font-size: 1.1rem;
        color: var(--secondary);
    }}
    .step-line {{
        position: absolute;
        top: 25px;
        left: 10%;
        right: 10%;
        height: 4px;
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
        z-index: 1;
        border-radius: 2px;
    }}
    .btn-primary {{
        background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
        color: white !important;
        border: none;
        padding: 12px 24px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s;
        width: 100%;
        text-align: center;
        display: block;
        margin: 10px 0;
    }}
    .btn-primary:hover {{
        transform: translateY(-3px);
        box-shadow: 0 6px 15px rgba(13, 71, 161, 0.3);
    }}
    .footer {{
        text-align: center;
        padding: 2rem 0;
        color: #666;
        font-size: 0.9rem;
        border-top: 1px solid #eee;
        margin-top: 3rem;
    }}
    .feature-list {{
        margin: 1.5rem 0;
        padding-left: 1.5rem;
    }}
    .feature-list li {{
        margin-bottom: 0.8rem;
        padding: 0.8rem;
        background: #f8fbff;
        border-radius: 8px;
        border-left: 3px solid var(--primary);
    }}
    .stats-card {{
        background: linear-gradient(90deg, #f0f7ff 0%, #e3f2fd 100%);
        padding: 1.2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
    }}
    .stats-number {{
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--secondary);
        line-height: 1;
    }}
    .stats-label {{
        font-size: 0.9rem;
        color: #666;
    }}
    .upload-area {{
        border: 2px dashed #ccc;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        transition: all 0.3s;
        background: #fafcff;
        margin-bottom: 1.5rem;
    }}
    .upload-area:hover {{
        border-color: var(--primary);
        background: #f0f7ff;
    }}
    .upload-icon {{
        font-size: 3rem;
        color: var(--primary);
        margin-bottom: 1rem;
    }}
    .preview-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
    }}
    .preview-table th {{
        background: var(--primary);
        color: white;
        padding: 12px;
        text-align: left;
    }}
    .preview-table td {{
        padding: 10px;
        border-bottom: 1px solid #eee;
    }}
    .preview-table tr:nth-child(even) {{
        background: #f9fbfe;
    }}
    .preview-table tr:hover {{
        background: #edf4ff;
    }}
    @media (max-width: 768px) {{
        .step-container {{
            flex-direction: column;
            gap: 30px;
        }}
        
        .step {{
            flex-direction: row;
            align-items: center;
            gap: 15px;
        }}
        
        .step-title {{
            text-align: left;
        }}
        
        .step-line {{
            display: none;
        }}
    }}
    .data-source-btn {{
        height: 280px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: center;
        padding: 25px 20px;
        border-radius: 16px;
        background: linear-gradient(135deg, #f0f7ff 0%, #e3f2fd 100%);
        border: 1px solid #bbdefb;
        box-shadow: 0 6px 15px rgba(0,0,0,0.08);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        text-align: center;
        margin-bottom: 25px;
        position: relative;
        overflow: hidden;
    }}
    .data-source-btn * {{
        text-align: center !important;
    }}
    .data-source-btn:hover {{
        transform: translateY(-10px) scale(1.02);
        box-shadow: 0 12px 30px rgba(30, 136, 229, 0.25);
        border-color: #1e88e5;
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
    }}
    .data-source-btn:active {{
        transform: translateY(-5px) scale(1.01);
    }}
    .btn-icon {{
        font-size: 3.5rem;
        margin-bottom: 20px;
        color: #0d47a1;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
    }}
    .data-source-btn:hover .btn-icon {{
        transform: scale(1.2);
        color: #1e88e5;
    }}
    .btn-title {{
        font-size: 1.4rem;
        font-weight: 700;
        color: #0d47a1;
        margin-bottom: 15px;
        width: 100%;
        text-align: center;
    }}
    .btn-subtitle {{
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 20px;
        flex-grow: 1;
        width: 100%;
        text-align: center;
    }}
    .btn-badge {{
        position: absolute;
        top: 15px;
        right: 15px;
        left: unset;
        background: #ff9800;
        color: white;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: bold;
        box-shadow: 0 3px 8px rgba(255,152,0,0.3);
        text-align: center;
    }}
    .btn-features {{
        text-align: center;
        width: 100%;
        padding: 12px 0;
        border-top: 1px dashed #bbdefb;
        margin-top: 15px;
        display: flex;
        flex-direction: column;
        gap: 2px;
        align-items: center;
    }}
    .btn-feature {{
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 8px 0;
        font-size: 0.97rem;
        width: 100%;
        text-align: center;
    }}
    .btn-feature i {{
        margin-left: 8px;
        color: #1e88e5;
    }}
    @media (max-width: 900px) {{
        .data-source-btn {{
            height: auto;
            padding: 20px 15px;
        }}
    }}
    /* تعليمات توضيحية أسفل البطاقات */
    .data-source-tip {{
        text-align: center;
        margin-top: 30px;
        color: #666;
        font-size: 1rem;
        font-family: var(--font);
        letter-spacing: 0.01em;
    }}
    </style>
    """, unsafe_allow_html=True)

def dynamic_stepper(current_step):
    steps = [
        {"num": 1, "title": "اختيار البيانات", "icon": "📥"},
        {"num": 2, "title": "معاينة البيانات", "icon": "🔍"},
        {"num": 3, "title": "ضبط الأوزان", "icon": "⚖️"},
        {"num": 4, "title": "الجدولة", "icon": "🚀"}
    ]
    stepper_html = f"""
    <style>
    @keyframes pulse {{
        0% {{ transform: scale(1); }}
        50% {{ transform: scale(1.1); }}
        100% {{ transform: scale(1); }}
    }}
    .stepper-container {{
        display: flex;
        justify-content: space-between;
        position: relative;
        margin: 40px 0;
        padding: 0 10%;
    }}
    .stepper-line {{
        position: absolute;
        top: 25px;
        left: 10%;
        right: 10%;
        height: 4px;
        background: linear-gradient(90deg, #1e88e5 0%, #0d47a1 100%);
        z-index: 1;
        border-radius: 2px;
        transition: all 0.5s ease;
    }}
    .stepper-step {{
        display: flex;
        flex-direction: column;
        align-items: center;
        z-index: 2;
        position: relative;
        cursor: pointer;
        transition: all 0.3s ease;
        flex: 1;
    }}
    .stepper-step:hover .stepper-number {{
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.2);
    }}
    .stepper-number {{
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: #e3f2fd;
        color: #0d47a1;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1.5rem;
        margin-bottom: 10px;
        transition: all 0.3s ease;
        position: relative;
        z-index: 2;
    }}
    .stepper-step.active .stepper-number {{
        background: linear-gradient(135deg, #1e88e5 0%, #0d47a1 100%);
        color: white;
        animation: pulse 2s infinite;
        box-shadow: 0 4px 20px rgba(30, 136, 229, 0.5);
    }}
    .stepper-step.completed .stepper-number {{
        background: linear-gradient(135deg, #66bb6a 0%, #388e3c 100%);
        color: white;
    }}
    .stepper-step.completed .stepper-number::after {{
        content: "✓";
        position: absolute;
        font-size: 1.8rem;
    }}
    .stepper-title {{
        font-weight: 600;
        text-align: center;
        font-size: 1.1rem;
        color: #333;
        padding: 5px 10px;
        border-radius: 10px;
        background: #f5f9ff;
        transition: all 0.3s ease;
    }}
    .stepper-step.active .stepper-title {{
        background: #0d47a1;
        color: white;
        transform: translateY(5px);
    }}
    @media (max-width: 768px) {{
        .stepper-container {{
            flex-direction: column;
            gap: 30px;
        }}
        .stepper-line {{
            display: none;
        }}
        .stepper-step {{
            flex-direction: row;
            align-items: center;
            gap: 15px;
        }}
        .stepper-title {{
            text-align: left;
        }}
    }}
    </style>
    <div class="stepper-container">
        <div class="stepper-line"></div>
        {''.join([
            f'''
            <div class="stepper-step 
                {'active' if step['num'] == current_step else 'completed' if step['num'] < current_step else ''}">
                <div class="stepper-number">{step['num']}</div>
                <div class="stepper-title">
                    {step['icon']} {step['title']}
                </div>
            </div>
            ''' for step in steps
        ])}
    </div>
    """
    html(stepper_html, height=120)

def show_contextual_guidance():
    guidance = {
        1: "📌 البداية: اختر مصدر البيانات المناسب لبدء عملية الجدولة",
        2: "🔍 المراجعة: تأكد من صحة البيانات قبل الانتقال للخطوة التالية",
        3: "⚖️ التخصيص: اضبط الأوزان حسب أولويات المؤسسة التعليمية",
        4: "🚀 التنفيذ: شاهد النتائج وقم بتصدير الجدول النهائي"
    }
    with st.expander("💡 دليل التوجيه السريع", expanded=True):
        st.info(guidance.get(st.session_state.current_step, ""))
        st.progress(min(1.0, (st.session_state.current_step - 1) * 0.33))

# ------ واجهة الخطوة 1: اختيار البيانات ------
def step_data_selection():
    load_custom_css()
    st.markdown("""
    <div class="header">
        <h1>نظام جدولة المحاضرات الجامعية</h1>
        <p>نظام ذكي ومتقدم لجدولة المحاضرات الجامعية مع مراعاة جميع القيود والتفضيلات</p>
    </div>
    """, unsafe_allow_html=True)
    dynamic_stepper(1)
    show_contextual_guidance()
    
    st.markdown("""
    <div class="card">
        <div class="card-title">
            <i>📥</i>
            <h3>الخطوة 1: اختيار مصدر البيانات</h3>
        </div>
        <p style="text-align:center; margin-bottom:30px; font-size:1.1rem">
            اختر الطريقة المناسبة لتحميل بيانات الجدولة
        </p>
        <div class="data-source-container">
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown("""
        <div class="data-source-btn">
            <span class="btn-badge">الخيار الأسرع</span>
            <div class="btn-icon">🧪</div>
            <div class="btn-title">البيانات التجريبية</div>
            <div class="btn-subtitle">بيانات جاهزة للاختبار السريع</div>
            <div class="btn-features">
                <div class="btn-feature"><i class="fas fa-check-circle"></i> لا يحتاج إلى تحميل</div>
                <div class="btn-feature"><i class="fas fa-check-circle"></i> مثال كامل متكامل</div>
                <div class="btn-feature"><i class="fas fa-check-circle"></i> بداية فورية</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("استخدام البيانات التجريبية", key="sample_btn", use_container_width=True):
            st.session_state.data_source = "sample"
            st.session_state.selected_data = load_sample_data()
            st.success("تم تحميل البيانات التجريبية بنجاح!")
            st.session_state.current_step = 2
            st.rerun()
    with col2:
        st.markdown("""
        <div class="data-source-btn">
            <span class="btn-badge">الأكثر مرونة</span>
            <div class="btn-icon">📁</div>
            <div class="btn-title">رفع ملف البيانات</div>
            <div class="btn-subtitle">تحميل ملف JSON مخصص</div>
            <div class="btn-features">
                <div class="btn-feature"><i class="fas fa-check-circle"></i> يدعم تنسيق JSON</div>
                <div class="btn-feature"><i class="fas fa-check-circle"></i> بيانات حقيقية</div>
                <div class="btn-feature"><i class="fas fa-check-circle"></i> حجم حتى 10MB</div>
            </div>
        </div>
        <div style='height: 24px;'></div>
        """, unsafe_allow_html=True)
        uploaded_file = st.file_uploader(" ", type=["json"], label_visibility="collapsed", accept_multiple_files=False, key="file_uploader")
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                valid, message = validate_json_structure(data)
                if not valid:
                    raise ValueError(f"خطأ في هيكل الملف: {message}")
                for room in data.get("rooms", []):
                    valid, message = validate_room_data(room)
                    if not valid:
                        raise ValueError(f"خطأ في بيانات القاعة: {message}")
                for instructor in data.get("instructors", []):
                    valid, message = validate_instructor_data(instructor)
                    if not valid:
                        raise ValueError(f"خطأ في بيانات المدرس: {message}")
                for group in data.get("groups", []):
                    valid, message = validate_group_data(group)
                    if not valid:
                        raise ValueError(f"خطأ في بيانات المجموعة: {message}")
                for course in data.get("courses", []):
                    valid, message = validate_course_data(course)
                    if not valid:
                        raise ValueError(f"خطأ في بيانات المادة: {message}")
                st.session_state.data_source = "file"
                st.session_state.original_data = deepcopy(data)
                st.session_state.selected_data = data
                st.session_state.current_file = uploaded_file.name
                st.success("تم رفع الملف بنجاح!")
                st.session_state.current_step = 2
                st.rerun()
            except Exception as e:
                error_msg = ErrorHandler.handle_error(e, context="رفع ملف البيانات")
                st.error(error_msg)
    with col3:
        st.markdown("""
        <div class="data-source-btn">
            <span class="btn-badge">الأكثر دقة</span>
            <div class="btn-icon">✏️</div>
            <div class="btn-title">الإدخال اليدوي</div>
            <div class="btn-subtitle">إدخال البيانات يدوياً</div>
            <div class="btn-features">
                <div class="btn-feature"><i class="fas fa-check-circle"></i> تحرير كامل</div>
                <div class="btn-feature"><i class="fas fa-check-circle"></i> التحقق من الجودة</div>
                <div class="btn-feature"><i class="fas fa-check-circle"></i> تحكم كامل</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("فتح إدارة البيانات", key="manual_btn", use_container_width=True):
            st.session_state.data_source = "manual"
            st.session_state.selected_data = {
                "rooms": [],
                "instructors": [],
                "groups": [],
                "courses": []
            }
            st.session_state.show_data_manager = True
            st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.markdown("""
    <div class="data-source-tip">
        <i class="fas fa-lightbulb"></i> نصيحة: يمكنك البدء بالبيانات التجريبية لتجربة النظام ثم استخدام بياناتك الخاصة
    </div>
    """, unsafe_allow_html=True)

# ------ واجهة الخطوة 2: معاينة البيانات ------
def step_data_preview():
    load_custom_css()
    st.markdown("""
    <div class="header">
        <h1>نظام جدولة المحاضرات الجامعية</h1>
        <p>نظام ذكي ومتقدم لجدولة المحاضرات الجامعية مع مراعاة جميع القيود والتفضيلات</p>
    </div>
    """, unsafe_allow_html=True)
    dynamic_stepper(2)
    show_contextual_guidance()
    
    st.markdown("""
    <div class="card">
        <div class="card-title">
            <i>🔍</i>
            <h3>الخطوة 2: معاينة البيانات والتحقق</h3>
        </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.selected_data is None:
        st.warning("لم يتم تحميل أي بيانات صالحة. الرجاء اختيار مصدر بيانات أولاً.")
        if st.button("العودة إلى الخطوة الأولى", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
        return
    
    # عرض معاينة البيانات
    st.subheader("📋 معاينة البيانات المحددة")
    data = st.session_state.selected_data
    with st.expander("القاعات", expanded=True):
        if data.get("rooms"):
            st.dataframe(pd.DataFrame(data["rooms"]))
        else:
            st.warning("لا توجد بيانات للقاعات")
    with st.expander("المدرسين"):
        if data.get("instructors"):
            st.dataframe(pd.DataFrame(data["instructors"]))
        else:
            st.warning("لا توجد بيانات للمدرسين")
    with st.expander("المجموعات"):
        if data.get("groups"):
            st.dataframe(pd.DataFrame(data["groups"]))
        else:
            st.warning("لا توجد بيانات للمجموعات")
    with st.expander("المواد"):
        if data.get("courses"):
            st.dataframe(pd.DataFrame(data["courses"]))
        else:
            st.warning("لا توجد بيانات للمواد")
    
    st.markdown("---")
    
    # أزرار التحكم
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄  تغيير مصدر البيانات", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
    with col2:
        if st.button("✏️ تعديل البيانات ", type="primary", use_container_width=True):
            st.session_state.show_data_manager = True
            st.rerun()
    with col3:
        if st.button("⚙️ الانتقال لضبط الأوزان", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    # زر الإعدادات المتقدمة منفصل
    if st.button("⚙️ الإعدادات المتقدمة", use_container_width=True):
        st.session_state.show_advanced_settings = True
        st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

# ------ واجهة الخطوة 3: ضبط الأوزان ------
def step_weights_adjustment():
    load_custom_css()
    st.markdown("""
    <div class="header">
        <h1>نظام جدولة المحاضرات الجامعية</h1>
        <p>نظام ذكي ومتقدم لجدولة المحاضرات الجامعية مع مراعاة جميع القيود والتفضيلات</p>
    </div>
    """, unsafe_allow_html=True)
    dynamic_stepper(3)
    show_contextual_guidance()
    
    st.markdown("""
    <div class="card">
        <div class="card-title">
            <i>⚖️</i>
            <h3>الخطوة 3: ضبط أوزان القيود</h3>
        </div>
    """, unsafe_allow_html=True)
    
    st.info("اضبط الأوزان حسب أهمية كل قيد في نظام الجدولة")
    
    tabs = st.tabs(["القيود الأساسية", "القيود الزمنية", "القيود المتقدمة"])
    
    with tabs[0]:
        st.subheader("القيود الأساسية")
        room_conflict = st.slider(
            "تعارض القاعات", 1, 10, 8, 
            help="أهمية تجنب تعيين قاعتين في نفس الوقت"
        )
        
        instructor_conflict = st.slider(
            "تعارض المدرسين", 1, 10, 9, 
            help="أهمية تجنب تعيين مدرس في محاضرتين في نفس الوقت"
        )
        
        group_conflict = st.slider(
            "تعارض المجموعات", 1, 10, 7, 
            help="أهمية تجنب تعيين مجموعة في محاضرتين في نفس الوقت"
        )
    
    with tabs[1]:
        st.subheader("القيود الزمنية")
        time_preference = st.slider(
            "تفضيلات الوقت", 1, 10, 6, 
            help="أهمية جدولة المحاضرات في الأوقات المفضلة"
        )
        
        min_break = st.slider(
            "فترات الراحة", 1, 10, 5, 
            help="أهمية وجود فترات راحة بين المحاضرات"
        )
        
        max_daily_hours = st.slider(
            "الحد الأقصى للساعات اليومية", 1, 10, 7, 
            help="أهمية عدم تجاوز عدد ساعات معين في اليوم"
        )
    
    with tabs[2]:
        st.subheader("القيود المتقدمة")
        facility_match = st.slider(
            "توافق المرافق", 1, 10, 6, 
            help="أهمية توافق مرافق القاعة مع متطلبات المادة"
        )
        
        instructor_preference = st.slider(
            "تفضيلات المدرسين", 1, 10, 4, 
            help="أهمية تلبية تفضيلات المدرسين"
        )
        
        room_utilization = st.slider(
            "استخدام القاعات", 1, 10, 5, 
            help="أهمية الاستخدام الأمثل للقاعات"
        )
    
    st.markdown("---")
    
    col1, col2 = st.columns([1,2])
    with col1:
        if st.button("⬅️ العودة للمعاينة", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()
            
    with col2:
        if st.button("🚀 بدء عملية الجدولة", type="primary", use_container_width=True):
            weights = {
                "room_conflict": room_conflict,
                "instructor_conflict": instructor_conflict,
                "group_conflict": group_conflict,
                "time_preference": time_preference,
                "min_break": min_break,
                "max_daily_hours": max_daily_hours,
                "facility_match": facility_match,
                "instructor_preference": instructor_preference,
                "room_utilization": room_utilization
            }
            st.session_state.config.penalty_weights = weights
            st.session_state.current_step = 4
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

# ------ واجهة الخطوة 4: الجدولة والنتائج ------
def step_scheduling():
    load_custom_css()
    st.markdown("""
    <div class="header">
        <h1>نظام جدولة المحاضرات الجامعية</h1>
        <p>نظام ذكي ومتقدم لجدولة المحاضرات الجامعية مع مراعاة جميع القيود والتفضيلات</p>
    </div>
    """, unsafe_allow_html=True)
    dynamic_stepper(4)
    show_contextual_guidance()
    
    st.markdown("""
    <div class="card">
        <div class="card-title">
            <i>🚀</i>
            <h3>الخطوة 4: الجدولة والنتائج</h3>
        </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.selected_data is None:
        st.warning("لم يتم تحميل أي بيانات صالحة. الرجاء اختيار مصدر بيانات أولاً.")
        if st.button("العودة إلى الخطوة الأولى", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
        return
    
    if st.button("🚀 بدء عملية الجدولة", type="primary", use_container_width=True):
        with st.spinner("جاري إنشاء الجدول الزمني الأمثل. قد يستغرق هذا بضع دقائق..."):

            try:
                data = st.session_state.selected_data
                config = config_manager.get_config()
                from model import Room, Instructor, Group, Course
                rooms = [Room(**r) for r in data["rooms"]]
                instructors = [Instructor(**i) for i in data["instructors"]]
                groups = [Group(**g) for g in data["groups"]]
                courses = [Course(**c) for c in data["courses"]]
                # نقاط تحقق متقدمة
                # st.info(f"[DEBUG] عدد القاعات: {len(rooms)}, المدرسين: {len(instructors)}, المجموعات: {len(groups)}, المواد: {len(courses)}")
                # st.info(f"[DEBUG] أول قاعة: {rooms[0].__dict__ if rooms else 'لا يوجد'}")
                # st.info(f"[DEBUG] أول مدرس: {instructors[0].__dict__ if instructors else 'لا يوجد'}")
                # st.info(f"[DEBUG] أول مجموعة: {groups[0].__dict__ if groups else 'لا يوجد'}")
                # st.info(f"[DEBUG] أول مادة: {courses[0].__dict__ if courses else 'لا يوجد'}")
                # st.info(f"[DEBUG] Config المستخدم: {config.__dict__ if hasattr(config, '__dict__') else str(config)}")
                
                from datetime import datetime, time as dtime
                # تحويل daily_start_time و daily_end_time إلى كائن وقت إذا كانت نص
                if isinstance(config.daily_start_time, str):
                    config.daily_start_time = datetime.strptime(config.daily_start_time, "%H:%M").time()
                if isinstance(config.daily_end_time, str):
                    config.daily_end_time = datetime.strptime(config.daily_end_time, "%H:%M").time()
                
                # تحويل working_days من نصوص إلى أرقام إذا لزم الأمر
                arabic_days = {
                    "السبت": 0,
                    "الأحد": 1,
                    "الاثنين": 2,
                    "الثلاثاء": 3,
                    "الأربعاء": 4,
                    "الخميس": 5,
                    "الجمعة": 6
                }
                if config.working_days and isinstance(config.working_days[0], str):
                    config.working_days = [arabic_days.get(d, d) for d in config.working_days]
                
                cp_scheduler = CPSatScheduler(config)
                initial_schedule = cp_scheduler.generate_schedule(courses, rooms, groups, instructors)
                if not initial_schedule:
                    st.error("تعذر إنشاء الجدول الزمني. يرجى مراجعة البيانات أو القيود.")
                    return
                optimizer = EnhancedGeneticOptimizer([initial_schedule], config)
                optimized_schedule, _ = optimizer.evolve()
                # حفظ كلا الجدولين في الجلسة
                st.session_state.schedule_initial = [
                    {
                        "course": s.assigned_course.name,
                        "instructor": s.assigned_instructor.name,
                        "group": s.group_id,
                        "room": s.assigned_room.name,
                        "day": str(s.time_slot.day.name) if hasattr(s.time_slot.day, 'name') else str(s.time_slot.day),
                        "start": s.time_slot.start_time.strftime('%H:%M'),
                        "end": s.time_slot.end_time.strftime('%H:%M')
                    }
                    for s in initial_schedule
                ]
                st.session_state.schedule_optimized = [
                    {
                        "course": s.assigned_course.name,
                        "instructor": s.assigned_instructor.name,
                        "group": s.group_id,
                        "room": s.assigned_room.name,
                        "day": str(s.time_slot.day.name) if hasattr(s.time_slot.day, 'name') else str(s.time_slot.day),
                        "start": s.time_slot.start_time.strftime('%H:%M'),
                        "end": s.time_slot.end_time.strftime('%H:%M')
                    }
                    for s in optimized_schedule
                ]
                # الافتراضي: عرض الجدول المحسن
                st.session_state.schedule = st.session_state.schedule_optimized
                st.success("تم إنشاء الجدول الزمني بنجاح!")
                st.balloons()
            except Exception as e:
                import traceback
                st.error(f"[ERROR] {ErrorHandler.handle_error(e, context='عملية الجدولة')}")
                st.error(traceback.format_exc())
                return
    
    if st.session_state.get("schedule_optimized") and st.session_state.get("schedule_initial"):
        st.subheader("اختيار الجدول المراد عرضه")
        algo_choice = st.radio(
            "اختر نوع الجدول:",
            ["الجدول المحسن (الجيني)", "الجدول الأولي (CP-SAT)"]
        )
        if algo_choice == "الجدول الأولي (CP-SAT)":
            schedule = st.session_state.schedule_initial
        else:
            schedule = st.session_state.schedule_optimized
        st.session_state.schedule = schedule
    else:
        schedule = st.session_state.schedule
    
    if st.session_state.get("schedule"):
        st.subheader("📅 الجدول الزمني النهائي")
        st.dataframe(pd.DataFrame(schedule))
        # زر عرض الجدول الزمني المتقدم
        if st.button("👁️ عرض الجدول الزمني المتقدم", use_container_width=True):
            st.session_state.show_timetable_viewer = True
            st.rerun()
        st.subheader("📊 إحصائيات الجدولة")
        # حساب القيم الحقيقية
        num_classes = len(schedule)
        rooms = st.session_state.selected_data.get("rooms", [])
        days = set([s["day"] for s in schedule])
        periods_per_day = len(set((s["start"], s["end"]) for s in schedule)) // len(days) if days else 1
        total_possible = max(1, len(rooms) * len(days) * periods_per_day)
        usage_percent = int((num_classes / total_possible) * 100) if total_possible else 0
        from utils.util import analyze_dict_conflicts
        conflicts = analyze_dict_conflicts(schedule)
        num_conflicts = sum(len(v) for t in conflicts.values() for v in t.values())
        instructors = st.session_state.selected_data.get("instructors", [])
        instructor_ids = [i["name"] for i in instructors]
        instructor_conflicts = conflicts.get("instructor", {})
        satisfied = sum(1 for i in instructor_ids if len(instructor_conflicts.get(i, [])) == 0)
        satisfaction = int((satisfied / len(instructor_ids)) * 100) if instructor_ids else 100
        room_ids = [r["name"] for r in rooms]
        room_conflicts = conflicts.get("room", {})
        efficient = sum(1 for r in room_ids if len(room_conflicts.get(r, [])) == 0)
        efficiency = int((efficient / len(room_ids)) * 100) if room_ids else 100
        quality = max(0, 100 - num_conflicts * 5)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("عدد المحاضرات", num_classes)
            st.metric("نسبة الاستخدام", f"{usage_percent}%")
        with col2:
            st.metric("عدد التعارضات", num_conflicts)
            st.metric("رضا المدرسين", f"{satisfaction}%")
        with col3:
            st.metric("كفاءة القاعات", f"{efficiency}%")
            st.metric("جودة الجدول", f"{quality}%")
        
        st.subheader("📤 تصدير الجدول")
        col_exp1, col_exp2, col_exp3 = st.columns(3)
        with col_exp1:
            st.download_button("💾 حفظ كملف Excel", data="", file_name="schedule.xlsx")
        with col_exp2:
            st.download_button("🖨️ حفظ كملف PDF", data="", file_name="schedule.pdf")
        with col_exp3:
            st.download_button("📝 حفظ كملف JSON", data="", file_name="schedule.json")
    
    st.markdown("---")
    if st.button("🔄 إنشاء جدول جديد", type="primary", use_container_width=True):
        st.session_state.current_step = 1
        st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

def main():
    if st.session_state.get("show_data_manager"):
        data_manager_main()
        return
    
    if st.session_state.get("show_advanced_settings"):
        advanced_settings_main()
        return
    
    if st.session_state.get("show_timetable_viewer"):
        timetable_viewer_main()
        return
    
    if st.session_state.current_step == 1:
        step_data_selection()
    elif st.session_state.current_step == 2:
        step_data_preview()
    elif st.session_state.current_step == 3:
        step_weights_adjustment()
    elif st.session_state.current_step == 4:
        step_scheduling()

if __name__ == "__main__":
    main()
