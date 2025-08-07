import traceback
import streamlit as st

class ErrorHandler:
    @staticmethod
    def handle_error(e, context=""):
        """معالجة الأخطاء وعرض رسائل ودية"""
        error_type = type(e).__name__
        
        # رسائل مخصصة لأنواع الأخطاء الشائعة
        custom_messages = {
            "JSONDecodeError": "ملف غير صالح - يرجى التحقق من صيغة JSON",
            "KeyError": "حقل مفقود في البيانات",
            "ValueError": "قيمة غير صالحة في البيانات",
            "TypeError": "نوع بيانات غير متطابق"
        }
        
        # الرسالة الأساسية
        message = custom_messages.get(error_type, "حدث خطأ غير متوقع")
        
        # التفاصيل الفنية
        tech_details = f"""
        **التفاصيل الفنية:**
        - نوع الخطأ: {error_type}
        - الرسالة: {str(e)}
        - السياق: {context}
        """
        
        # لوحة تفاعلية للتفاصيل
        with st.expander("تفاصيل الخطأ التقنية"):
            st.code(traceback.format_exc())
        
        return f"""
        ⚠️ **{message}**
        
        {tech_details}
        
        **الإجراءات المقترحة:**
        1. التحقق من صحة البيانات المدخلة
        2. مراجعة ملف السجلات للتفاصيل
        3. التواصل مع الدعم الفني إذا تكرر الخطأ
        """
