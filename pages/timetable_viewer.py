import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.util import analyze_dict_conflicts, create_gantt_chart
from utils.analytics import ScheduleAnalytics
from utils.error_handler import ErrorHandler
import base64
import json
import tempfile
import matplotlib.pyplot as plt
from fpdf import FPDF
from icalendar import Calendar, Event
import pytz
import logging

# إعدادات تسجيل الدخول
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

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
    
    .stats-container {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin-bottom: 2rem;
    }}
    
    .stat-card {{
        background: linear-gradient(135deg, #f0f7ff 0%, #e3f2fd 100%);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        border-left: 4px solid var(--primary);
    }}
    
    .stat-number {{
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--secondary);
        line-height: 1;
        margin-bottom: 5px;
    }}
    
    .stat-label {{
        font-size: 0.9rem;
        color: #666;
    }}
    
    .filter-bar {{
        display: flex;
        gap: 15px;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }}
    
    .filter-item {{
        flex: 1;
        min-width: 200px;
    }}
    
    .export-bar {{
        display: flex;
        gap: 10px;
        margin-top: 2rem;
        flex-wrap: wrap;
    }}
    
    .export-button {{
        flex: 1;
        min-width: 150px;
        text-align: center;
        padding: 12px;
        background: var(--primary);
        color: white;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
    }}
    
    .export-button:hover {{
        background: var(--secondary);
        transform: translateY(-3px);
        box-shadow: 0 4px 10px rgba(13, 71, 161, 0.3);
    }}
    
    .tab-container {{
        margin-top: 1.5rem;
    }}
    
    .schedule-card {{
        background: linear-gradient(135deg, #f8fbff 0%, #edf5ff 100%);
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        border-left: 4px solid var(--primary);
    }}
    
    .schedule-card h4 {{
        margin-top: 0;
        color: var(--secondary);
    }}
    
    .schedule-details {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
        margin-top: 10px;
    }}
    
    .schedule-item {{
        background: rgba(255, 255, 255, 0.7);
        padding: 8px;
        border-radius: 8px;
    }}
    
    .schedule-item-label {{
        font-size: 0.8rem;
        color: #666;
    }}
    
    .schedule-item-value {{
        font-weight: 600;
        font-size: 1rem;
    }}
    
    .conflict-badge {{
        background: #ff5252;
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        margin-left: 8px;
    }}
    
    @media (max-width: 768px) {{
        .stats-container {{
            grid-template-columns: 1fr;
        }}
        
        .filter-bar {{
            flex-direction: column;
        }}
        
        .export-bar {{
            flex-direction: column;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

# ------ وظائف مساعدة للتصدير ------
def generate_excel(df):
    """إنشاء ملف Excel من DataFrame"""
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def generate_pdf(df):
    """إنشاء ملف PDF من DataFrame"""
    from fpdf import FPDF
    from io import BytesIO
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # إضافة عنوان
    pdf.cell(200, 10, txt="الجدول الزمني للمحاضرات", ln=True, align='C')
    
    # إضافة التاريخ
    pdf.cell(200, 10, txt=datetime.now().strftime("%Y-%m-%d %H:%M"), ln=True, align='C')
    
    # إضافة الجدول
    col_width = 40
    row_height = 10
    headers = ["المادة", "المدرس", "المجموعة", "القاعة", "اليوم", "الوقت"]
    
    # إضافة رؤوس الأعمدة
    for header in headers:
        pdf.cell(col_width, row_height, txt=header, border=1)
    pdf.ln(row_height)
    
    # إضافة البيانات
    for _, row in df.iterrows():
        pdf.cell(col_width, row_height, txt=row['course'], border=1)
        pdf.cell(col_width, row_height, txt=row['instructor'], border=1)
        pdf.cell(col_width, row_height, txt=row['group'], border=1)
        pdf.cell(col_width, row_height, txt=row['room'], border=1)
        pdf.cell(col_width, row_height, txt=row['day'], border=1)
        pdf.cell(col_width, row_height, txt=f"{row['start']} - {row['end']}", border=1)
        pdf.ln(row_height)
    
    output = BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

def generate_ical(df):
    """إنشاء ملف iCal من DataFrame"""
    cal = Calendar()
    cal.add('prodid', '-//University Schedule//ar-sa//')
    cal.add('version', '2.0')
    
    timezone = pytz.timezone('Asia/Riyadh')
    
    # خريطة الأيام العربية إلى أيام الأسبوع الرقمية
    day_map = {
        'السبت': 0, 'الأحد': 1, 'الاثنين': 2, 
        'الثلاثاء': 3, 'الأربعاء': 4, 'الخميس': 5, 'الجمعة': 6
    }
    
    for _, row in df.iterrows():
        event = Event()
        event.add('summary', f"{row['course']} - {row['instructor']}")
        event.add('location', row['room'])
        
        # تحويل اليوم إلى رقم
        day_num = day_map.get(row['day'], 0)
        
        # افترض أننا نستخدم الأسبوع الحالي
        today = datetime.now()
        days_ahead = day_num - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        
        event_date = today + timedelta(days=days_ahead)
        
        # تحويل وقت البدء
        start_time = datetime.strptime(row['start'], '%H:%M').time()
        start_dt = datetime.combine(event_date, start_time)
        start_dt = timezone.localize(start_dt)
        
        # تحويل وقت الانتهاء
        end_time = datetime.strptime(row['end'], '%H:%M').time()
        end_dt = datetime.combine(event_date, end_time)
        end_dt = timezone.localize(end_dt)
        
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('description', f"المجموعة: {row['group']}")
        
        cal.add_component(event)
    
    return cal.to_ical()

# ------ واجهة الجدول الزمني ------
def main():
    # تحميل التصميم المخصص
    load_custom_css()
    
    # رأس الصفحة
    st.markdown(f"""
    <div class="header">
        <h1>الجدول الزمني - نظام جدولة المحاضرات</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # التحقق من وجود بيانات الجدول
    if "schedule" not in st.session_state or not st.session_state.schedule:
        st.error("""
        ⚠️ لا توجد بيانات مجدولة متاحة. 
        يرجى العودة إلى الصفحة الرئيسية وتوليد الجدول أولاً
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ العودة للصفحة الرئيسية", use_container_width=True):
                st.session_state.show_timetable_viewer = False
                st.switch_page("streamlit_app.py")
        with col2:
            if st.button("🔄 إعادة توليد الجدول", use_container_width=True, type="primary"):
                if "selected_data" in st.session_state:
                    from utils.util import generate_schedule
                    st.session_state.schedule = generate_schedule(st.session_state.selected_data)
                    st.rerun()
        return
    
    # تحويل الجدول إلى DataFrame
    schedule = st.session_state.schedule
    df = pd.DataFrame(schedule)
    
    # تحليل التعارضات
    if 'conflicts' not in st.session_state:
        st.session_state.conflicts = analyze_dict_conflicts(schedule)
    
    total_conflicts = 0
    for conflict_type in ['room', 'instructor', 'group']:
        for conflicts in st.session_state.conflicts[conflict_type].values():
            total_conflicts += len(conflicts)
    
    # ------ إحصائيات سريعة ------
    st.subheader("📊 ملخص الجدول الزمني")
    st.markdown(f"""
    <div class="stats-container">
        <div class="stat-card">
            <div class="stat-number">{len(df)}</div>
            <div class="stat-label">إجمالي المحاضرات</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{total_conflicts}</div>
            <div class="stat-label">عدد التعارضات</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{df['room'].nunique()}</div>
            <div class="stat-label">عدد القاعات</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{df['instructor'].nunique()}</div>
            <div class="stat-label">عدد المدرسين</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ------ شريط التصفية ------
    st.subheader("🔍 تصفية الجدول")
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns([1,1,1,1])
    
    with col1:
        day_filter = st.selectbox("اليوم", ["الكل"] + list(df["day"].unique()))
    
    with col2:
        group_filter = st.selectbox("المجموعة", ["الكل"] + list(df["group"].unique()))
    
    with col3:
        instructor_filter = st.selectbox("المدرس", ["الكل"] + list(df["instructor"].unique()))
    
    with col4:
        room_filter = st.selectbox("القاعة", ["الكل"] + list(df["room"].unique()))
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # تطبيق التصفية
    filtered_df = df.copy()
    
    if day_filter != "الكل":
        filtered_df = filtered_df[filtered_df["day"] == day_filter]
    
    if group_filter != "الكل":
        filtered_df = filtered_df[filtered_df["group"] == group_filter]
    
    if instructor_filter != "الكل":
        filtered_df = filtered_df[filtered_df["instructor"] == instructor_filter]
    
    if room_filter != "الكل":
        filtered_df = filtered_df[filtered_df["room"] == room_filter]
    
    # ------ عرض الجدول المصفى بطريقة بطاقات ------
    st.subheader("📅 المحاضرات المجدولة")
    
    if filtered_df.empty:
        st.warning("⚠️ لا توجد محاضرات تطابق معايير التصفية المحددة")
    else:
        for _, row in filtered_df.iterrows():
            conflict_count = 0
            conflict_text = ""
            
            # دالة مساعدة لمقارنة محاضرتين (row و dict)
            def is_same_lecture(row, lecture_dict):
                return (
                    row['course'] == lecture_dict['course'] and
                    row['group'] == lecture_dict['group'] and
                    row['room'] == lecture_dict['room'] and
                    row['instructor'] == lecture_dict['instructor'] and
                    row['day'] == lecture_dict['day'] and
                    row['start'] == lecture_dict['start'] and
                    row['end'] == lecture_dict['end']
                )
            
            # التحقق من التعارضات لهذه المحاضرة
            for conflict_type in ['room', 'instructor', 'group']:
                if row['room'] in st.session_state.conflicts[conflict_type]:
                    for conflict in st.session_state.conflicts[conflict_type][row['room']]:
                        if is_same_lecture(row, conflict[0]) or is_same_lecture(row, conflict[1]):
                            conflict_count += 1
                if row['instructor'] in st.session_state.conflicts[conflict_type]:
                    for conflict in st.session_state.conflicts[conflict_type][row['instructor']]:
                        if is_same_lecture(row, conflict[0]) or is_same_lecture(row, conflict[1]):
                            conflict_count += 1
                if row['group'] in st.session_state.conflicts[conflict_type]:
                    for conflict in st.session_state.conflicts[conflict_type][row['group']]:
                        if is_same_lecture(row, conflict[0]) or is_same_lecture(row, conflict[1]):
                            conflict_count += 1
            
            if conflict_count > 0:
                conflict_text = f"<span class='conflict-badge'>{conflict_count} تعارض</span>"
            
            st.markdown(f"""
            <div class="schedule-card">
                <h4>{row['course']} {conflict_text}</h4>
                <div class="schedule-details">
                    <div class="schedule-item">
                        <div class="schedule-item-label">المدرس</div>
                        <div class="schedule-item-value">{row['instructor']}</div>
                    </div>
                    <div class="schedule-item">
                        <div class="schedule-item-label">المجموعة</div>
                        <div class="schedule-item-value">{row['group']}</div>
                    </div>
                    <div class="schedule-item">
                        <div class="schedule-item-label">القاعة</div>
                        <div class="schedule-item-value">{row['room']}</div>
                    </div>
                    <div class="schedule-item">
                        <div class="schedule-item-label">اليوم</div>
                        <div class="schedule-item-value">{row['day']}</div>
                    </div>
                    <div class="schedule-item">
                        <div class="schedule-item-label">الوقت</div>
                        <div class="schedule-item-value">{row['start']} - {row['end']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # ------ التحليل البصري المتقدم ------
    st.subheader("📊 التحليل البصري المتقدم")
    
    tab1, tab2, tab3 = st.tabs(["مخطط جانت", "تحليل التعارضات", "إحصائيات مفصلة"])
    
    with tab1:
        st.subheader("مخطط جانت الزمني")
        col1, col2 = st.columns(2)
        with col1:
            group_sel = st.selectbox("اختر مجموعة:", [""] + list(df['group'].unique()), key="gantt_group")
        with col2:
            room_sel = st.selectbox("اختر قاعة:", [""] + list(df['room'].unique()), key="gantt_room")
        
        if group_sel:
            fig, error = create_gantt_chart(df, group_sel)
            if error:
                st.error(error)
            else:
                st.pyplot(fig)
        elif room_sel:
            # إنشاء مخطط جانت للقاعة المحددة
            room_df = df[df['room'] == room_sel]
            if not room_df.empty:
                # تحويل الأيام إلى أرقام متسلسلة للرسم
                day_order = {
                    "السبت": 0,
                    "الأحد": 1,
                    "الاثنين": 2,
                    "الثلاثاء": 3,
                    "الأربعاء": 4,
                    "الخميس": 5,
                    "الجمعة": 6
                }
                
                room_df['day_order'] = room_df['day'].map(day_order)
                
                # إنشاء الشكل
                fig = go.Figure()
                
                # إضافة شريط لكل محاضرة
                for _, row in room_df.iterrows():
                    # تحويل الوقت إلى دقائق
                    start_minutes = int(row['start'].split(':')[0]) * 60 + int(row['start'].split(':')[1])
                    end_minutes = int(row['end'].split(':')[0]) * 60 + int(row['end'].split(':')[1])
                    duration = end_minutes - start_minutes
                    
                    fig.add_trace(go.Bar(
                        y=[row['day']],
                        x=[duration],
                        base=start_minutes,
                        orientation='h',
                        name=row['course'],
                        hoverinfo='text',
                        hovertext=f"<b>{row['course']}</b><br>المجموعة: {row['group']}<br>المدرس: {row['instructor']}<br>الوقت: {row['start']} - {row['end']}",
                        marker_color=PRIMARY_COLOR
                    ))
                
                fig.update_layout(
                    barmode='stack',
                    title=f'جدول القاعة: {room_sel}',
                    height=500,
                    xaxis_title="الوقت",
                    yaxis_title="اليوم",
                    showlegend=False,
                    xaxis=dict(
                        tickmode='array',
                        tickvals=list(range(0, 24*60, 60)),
                        ticktext=[f"{h:02d}:00" for h in range(24)]
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("لا توجد محاضرات في هذه القاعة")
        else:
            st.info("يرجى اختيار مجموعة أو قاعة لعرض مخطط جانت")
    
    with tab2:
        st.subheader("تحليل التعارضات")
        if total_conflicts > 0:
            # إنشاء مخطط لتحليل التعارضات
            conflict_data = []
            for conflict_type, conflicts in st.session_state.conflicts.items():
                for resource, conflict_list in conflicts.items():
                    conflict_data.append({
                        "الموارد": resource,
                        "عدد التعارضات": len(conflict_list),
                        "النوع": conflict_type
                    })
            
            conflict_df = pd.DataFrame(conflict_data)
            
            if not conflict_df.empty:
                fig = px.bar(
                    conflict_df, 
                    x="الموارد", 
                    y="عدد التعارضات",
                    color="النوع",
                    barmode="group",
                    title="تحليل التعارضات في الجدول",
                    height=500,
                    text="عدد التعارضات",
                    color_discrete_map={
                        "room": "#FF5252",
                        "instructor": "#4FC3F7",
                        "group": "#66BB6A"
                    }
                )
                fig.update_layout(
                    template="plotly_white",
                    legend_title="نوع التعارض",
                    xaxis_title="الموارد",
                    yaxis_title="عدد التعارضات",
                    hovermode="x unified"
                )
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("تفاصيل التعارضات")
            for conflict_type, conflicts in st.session_state.conflicts.items():
                if conflicts:
                    st.write(f"### تعارضات {conflict_type}")
                    for resource, conflict_list in conflicts.items():
                        if conflict_list:
                            st.write(f"**{resource}**:")
                            for i, (lecture1, lecture2) in enumerate(conflict_list, 1):
                                st.write(f"{i}. تعارض بين:")
                                st.write(f"   - {lecture1['course']} ({lecture1['group']}) في {lecture1['room']} - {lecture1['day']} {lecture1['start']}-{lecture1['end']}")
                                st.write(f"   - {lecture2['course']} ({lecture2['group']}) في {lecture2['room']} - {lecture2['day']} {lecture2['start']}-{lecture2['end']}")
        else:
            st.success("🎉 تهانينا! لا توجد تعارضات في الجدول الزمني")
    
    with tab3:
        st.subheader("إحصائيات مفصلة")
        col1, col2 = st.columns(2)
        
        with col1:
            # توزيع المحاضرات على الأيام
            day_dist = df['day'].value_counts().reset_index()
            day_dist.columns = ['day', 'classes']
            fig1 = px.bar(day_dist, x='day', y='classes', title='توزيع المحاضرات على أيام الأسبوع')
            st.plotly_chart(fig1, use_container_width=True)
            
            # استخدام القاعات
            room_usage = df['room'].value_counts().reset_index()
            room_usage.columns = ['room', 'classes']
            fig3 = px.treemap(room_usage, path=['room'], values='classes', title='توزيع استخدام القاعات')
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            # عبء المدرسين
            inst_load = df['instructor'].value_counts().reset_index()
            inst_load.columns = ['instructor', 'classes']
            fig2 = px.bar(x=inst_load['instructor'], y=inst_load['classes'], title='عبء العمل على المدرسين')
            st.plotly_chart(fig2, use_container_width=True)
            
            # مخطط دائري للمجموعات
            group_dist = df['group'].value_counts().reset_index()
            group_dist.columns = ['group', 'classes']
            fig4 = px.pie(group_dist, names='group', values='classes', title='توزيع المحاضرات على المجموعات')
            st.plotly_chart(fig4, use_container_width=True)
    
    # ------ التقرير الإحصائي المتقدم ------
    if st.session_state.get("schedule"):
        try:
            analytics = ScheduleAnalytics(st.session_state.schedule)
            report = analytics.generate_summary_report()
            with st.expander("التقرير الإحصائي المتقدم"):
                st.plotly_chart(report["rooms_utilization"])
                st.plotly_chart(report["instructor_load"])
                st.plotly_chart(report["daily_distribution"])
                st.write(report["conflict_analysis"])
        except Exception as e:
            error_msg = ErrorHandler.handle_error(e, context="عرض الجدول الزمني")
            st.error(error_msg)
    
    # ------ تصدير الجدول ------
    st.subheader("📤 تصدير الجدول")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("💾 Excel", use_container_width=True, key="export_excel"):
            excel_data = generate_excel(df)
            st.download_button(
                label="⬇️ تنزيل Excel",
                data=excel_data,
                file_name="الجدول_الزمني.xlsx",
                mime="application/vnd.ms-excel"
            )
    
    with col2:
        if st.button("🖨️ PDF", use_container_width=True, key="export_pdf"):
            pdf_data = generate_pdf(df)
            st.download_button(
                label="⬇️ تنزيل PDF",
                data=pdf_data,
                file_name="الجدول_الزمني.pdf",
                mime="application/pdf"
            )
    
    with col3:
        if st.button("📝 JSON", use_container_width=True, key="export_json"):
            json_data = df.to_json(orient='records', force_ascii=False)
            st.download_button(
                label="⬇️ تنزيل JSON",
                data=json_data,
                file_name="الجدول_الزمني.json",
                mime="application/json"
            )
    
    with col4:
        if st.button("📅 iCal", use_container_width=True, key="export_ical"):
            ical_data = generate_ical(df)
            st.download_button(
                label="⬇️ تنزيل iCal",
                data=ical_data,
                file_name="الجدول_الزمني.ics",
                mime="text/calendar"
            )
    
    # زر العودة
    st.markdown("---")
    if st.button("⬅️ العودة للواجهة الرئيسية", use_container_width=True):
        st.session_state.show_timetable_viewer = False
        st.switch_page("streamlit_app.py")

# ------ تشغيل التطبيق ------
if __name__ == "__main__":
    main()