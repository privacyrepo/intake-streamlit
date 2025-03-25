# app.py
import os
import json
import base64
from typing import Dict, List, Optional, Any
import chainlit as cl
from chainlit.types import AskFileResponse
from chainlit.element import Element
import openai
from openai import OpenAI
import httpx
from pydantic import BaseModel, Field
import pandas as pd

# Initialize OpenAI client with explicit HTTP settings to avoid proxy issues
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    http_client=httpx.Client(
        base_url="https://api.openai.com/v1",
        follow_redirects=True,
        # No proxies configuration
    )
)

# RioContent class for multilingual message management
class RioContent:
    def __init__(self):
        self.messages = {
            "en": {
                # Welcome messages
                "welcome": "👋 Hello! 🌟 I'm Rio, your friendly insurance helper! I'm here to make getting your commercial auto insurance quote quick, easy, and stress-free! 🚗💨 Let's get started!",
                "language_selection": "First, what language would you prefer to use today?",
                
                # Document upload messages
                "nys_license_intro": "Great choice! To start, please upload your New York State Driver License. This will help me quickly gather your personal and license details.",
                "nys_license_confirm": "Fantastic! Thank you for confirming your NYS Driver License information.",
                "tlc_license_intro": "Next up, please upload a clear image of your Taxi and Limousine Commission (TLC) Hack License.",
                "tlc_license_confirm": "Perfect! Thank you for confirming your TLC Hack License information.",
                "vehicle_title_intro": "You're doing great! Now, please upload a clear image of your Vehicle Certificate of Title.",
                "vehicle_title_review": "Awesome! Let's review the extracted information and make any necessary edits.",
                "vehicle_title_confirm": "Thank you for confirming your Vehicle Title information.",
                
                # Contact information
                "contact_info_intro": "Almost done! I just need your contact information to complete your application.",
                "phone_request": "First, could you please provide your phone number?",
                "email_request": "Great! Now, could you please provide your email address?",
                
                # Radio base
                "radio_base_intro": "Great! Please upload your Radio Base Certification Letter next.",
                "radio_base_select": "Fantastic! Please select your affiliated Radio Base from the options provided.",
                
                # Review and confirmation
                "review_intro": "Here's a summary of all the information I've collected. Please review it carefully.",
                "confirm_question": "Is this information correct? Would you like to submit your application?",
                "edit_option": "Would you like to edit any of this information?",
                "processing": "Processing your application... ⏳",
                "submission_success": "✅ Wonderful! 🚀 You've successfully submitted your Commercial Auto Insurance application!",
                "submission_details": f"""
## Application Submitted

Thank you so much for providing all your details! 🥳 

Our team will review your information and reach out within 2 business days.
You will receive a confirmation email shortly with all the details of your application.

If you have any questions in the meantime, just ask—I'm always happy to help! 😊
                """,
                
                # Errors and processing
                "processing_document": "Processing your document... Please wait. This usually takes about 10-15 seconds. ⏳",
                "document_success": "✅ Document processed successfully!",
                "document_error": "❌ There was an issue processing your document. Would you like to try again or enter the information manually?",
                "confirmation_number": "Your confirmation number: APP-",
                
                # Actions
                "btn_confirm": "✅ Confirm",
                "btn_edit": "✏️ Edit",
                "btn_submit": "🚀 Submit Application",
                "btn_edit_info": "✏️ Edit Information",
                "btn_retry": "🔄 Try Again", 
                "btn_manual": "✍️ Enter Manually",
                "btn_english": "English",
                "btn_spanish": "Español",
                "btn_chinese": "中文",
                
                # Additional questions
                "owned_by_self": "Is this vehicle owned and operated only by yourself or spouse?",
                "named_drivers": "Is this vehicle operated by approved Named Drivers?",
                "workers_comp": "Do you currently carry workers compensation?",
                "radio_base": "Do you obtain fares via Radio Base?",
                
                # Misc
                "information_updated": "Information updated. Thank you!",
                "new_application": "Submit Another Application",
                "exit": "Exit",
                "restart": "Starting a new application...",
                "invalid_option": "Invalid option. Returning to review."
            },
            "es": {
                # Welcome messages
                "welcome": "👋 ¡Hola! 🌟 Soy Rio, tu amigable ayudante de seguros. Estoy aquí para hacer que obtener tu cotización de seguro de auto comercial sea rápido, fácil y sin estrés. 🚗💨 ¡Vamos a empezar!",
                "language_selection": "Primero, ¿qué idioma prefieres utilizar hoy?",
                
                # Document upload messages
                "nys_license_intro": "¡Excelente elección! Para comenzar, por favor sube una imagen clara de tu licencia de conducir del estado de Nueva York. Esto me ayudará a obtener rápidamente tus datos personales y detalles de la licencia.",
                "nys_license_confirm": "¡Fantástico! Gracias por confirmar la información de tu licencia de conducir del estado de NY.",
                "tlc_license_intro": "Ahora, por favor sube una imagen clara de tu licencia TLC (Taxi and Limousine Commission).",
                "tlc_license_confirm": "¡Perfecto! Gracias por confirmar la información de tu licencia TLC.",
                "vehicle_title_intro": "¡Lo estás haciendo muy bien! Ahora, por favor sube una imagen clara del certificado de título de tu vehículo.",
                "vehicle_title_review": "¡Genial! Revisemos la información extraída y hagamos las correcciones necesarias.",
                "vehicle_title_confirm": "Gracias por confirmar la información del título de tu vehículo.",
                
                # Contact information
                "contact_info_intro": "¡Ya casi terminamos! Solo necesito tu información de contacto para completar tu solicitud.",
                "phone_request": "Primero, ¿podrías proporcionarme tu número de teléfono, por favor?",
                "email_request": "¡Excelente! Ahora, ¿podrías proporcionarme tu dirección de correo electrónico?",
                
                # Radio base
                "radio_base_intro": "¡Muy bien! Por favor sube tu carta de certificación de la base de radio.",
                "radio_base_select": "¡Fantástico! Ahora selecciona tu base de radio afiliada de las opciones proporcionadas.",
                
                # Review and confirmation
                "review_intro": "Aquí hay un resumen de toda la información que he recopilado. Por favor, revísala cuidadosamente.",
                "confirm_question": "¿Es correcta esta información? ¿Te gustaría enviar tu solicitud?",
                "edit_option": "¿Te gustaría editar alguna de esta información?",
                "processing": "Procesando tu solicitud... ⏳",
                "submission_success": "✅ ¡Maravilloso! 🚀 ¡Has enviado con éxito tu solicitud de seguro de auto comercial!",
                "submission_details": f"""
## Solicitud Enviada

¡Muchas gracias por proporcionar todos tus datos! 🥳 

Nuestro equipo revisará tu información y se comunicará contigo en un plazo de 2 días hábiles.
Pronto recibirás un correo electrónico de confirmación con todos los detalles.

Si tienes alguna pregunta mientras tanto, no dudes en consultarme, ¡siempre estoy feliz de ayudar! 😊
                """,
                
                # Errors and processing
                "processing_document": "Procesando tu documento... Por favor espera. Esto normalmente toma entre 10-15 segundos. ⏳",
                "document_success": "✅ ¡Documento procesado con éxito!",
                "document_error": "❌ Hubo un problema al procesar tu documento. ¿Te gustaría intentarlo de nuevo o ingresar la información manualmente?",
                "confirmation_number": "Tu número de confirmación: APP-",
                
                # Actions
                "btn_confirm": "✅ Confirmar",
                "btn_edit": "✏️ Editar",
                "btn_submit": "🚀 Enviar Solicitud",
                "btn_edit_info": "✏️ Editar Información",
                "btn_retry": "🔄 Intentar de Nuevo", 
                "btn_manual": "✍️ Ingresar Manualmente",
                "btn_english": "English",
                "btn_spanish": "Español",
                "btn_chinese": "中文",
                
                # Additional questions
                "owned_by_self": "¿Este vehículo es propiedad y está operado únicamente por ti o tu cónyuge?",
                "named_drivers": "¿Este vehículo es operado por conductores nombrados aprobados?",
                "workers_comp": "¿Actualmente tienes compensación para trabajadores?",
                "radio_base": "¿Obtienes tarifas a través de una base de radio?",
                
                # Misc
                "information_updated": "Información actualizada. ¡Gracias!",
                "new_application": "Enviar Otra Solicitud",
                "exit": "Salir",
                "restart": "Comenzando una nueva solicitud...",
                "invalid_option": "Opción inválida. Volviendo a la revisión."
            },
            "zh": {
                # Welcome messages
                "welcome": "👋 你好！🌟 我是Rio，您友好的保险助手！我在这里帮助您快速、轻松、无压力地获取商业汽车保险报价！🚗💨 让我们开始吧！",
                "language_selection": "首先，您今天想使用哪种语言？",
                
                # Document upload messages
                "nys_license_intro": "很好的选择！首先，请上传您的纽约州驾驶执照。这将帮助我快速获取您的个人和执照详细信息。",
                "nys_license_confirm": "太棒了！感谢您确认您的纽约州驾驶执照信息。",
                "tlc_license_intro": "接下来，请上传您的出租车和豪华轿车委员会(TLC)执照的清晰图像。",
                "tlc_license_confirm": "完美！感谢您确认您的TLC执照信息。",
                "vehicle_title_intro": "您做得很好！现在，请上传您的车辆所有权证明的清晰图像。",
                "vehicle_title_review": "太好了！让我们检查提取的信息并进行必要的编辑。",
                "vehicle_title_confirm": "感谢您确认您的车辆所有权信息。",
                
                # Contact information
                "contact_info_intro": "几乎完成了！我只需要您的联系信息来完成您的申请。",
                "phone_request": "首先，请提供您的电话号码？",
                "email_request": "很好！现在，请提供您的电子邮件地址？",
                
                # Radio base
                "radio_base_intro": "太好了！请接下来上传您的无线电基地认证信。",
                "radio_base_select": "太棒了！请从提供的选项中选择您所属的无线电基地。",
                
                # Review and confirmation
                "review_intro": "以下是我收集的所有信息的摘要。请仔细检查。",
                "confirm_question": "这些信息正确吗？您想提交您的申请吗？",
                "edit_option": "您想编辑其中的任何信息吗？",
                "processing": "正在处理您的申请... ⏳",
                "submission_success": "✅ 太棒了！🚀 您已成功提交商业汽车保险申请！",
                "submission_details": f"""
## 申请已提交

非常感谢您提供所有详细信息！🥳 

我们的团队将审核您的信息并在2个工作日内与您联系。
您很快会收到一封包含所有详细信息的确认电子邮件。

如果您同时有任何问题，请随时询问——我很乐意帮忙！😊
                """,
                
                # Errors and processing
                "processing_document": "正在处理您的文档...请稍候。这通常需要约10-15秒。⏳",
                "document_success": "✅ 文档处理成功！",
                "document_error": "❌ 处理您的文档时出现问题。您想重试还是手动输入信息？",
                "confirmation_number": "您的确认号码：APP-",
                
                # Actions
                "btn_confirm": "✅ 确认",
                "btn_edit": "✏️ 编辑",
                "btn_submit": "🚀 提交申请",
                "btn_edit_info": "✏️ 编辑信息",
                "btn_retry": "🔄 重试", 
                "btn_manual": "✍️ 手动输入",
                "btn_english": "English",
                "btn_spanish": "Español",
                "btn_chinese": "中文",
                
                # Additional questions
                "owned_by_self": "这辆车是仅由您自己或配偶拥有和操作的吗？",
                "named_drivers": "这辆车是由经批准的指定驾驶员操作的吗？",
                "workers_comp": "您目前是否有工人赔偿保险？",
                "radio_base": "您是否通过无线电基地获取车费？",
                
                # Misc
                "information_updated": "信息已更新。谢谢！",
                "new_application": "提交另一份申请",
                "exit": "退出",
                "restart": "开始新的申请...",
                "invalid_option": "选项无效。返回审核。"
            }
        }
    
    def get(self, key, language="en"):
        """Get a message by key in the specified language"""
        if language not in self.messages:
            # Fallback to English if language not supported
            language = "en"
        
        return self.messages[language].get(key, self.messages["en"].get(key, ""))

# Initialize Rio content manager
rio = RioContent()

# Define document types
DOCUMENT_TYPES = {
    "nys_license": "NYS Driver License",
    "tlc_license": "TLC Hack License",
    "vehicle_title": "Vehicle Certificate of Title",
    "radio_base_cert": "Radio Base Certification Letter"
}

# Define data models
class PersonalInfo(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class LicenseInfo(BaseModel):
    nys_license_number: Optional[str] = None
    tlc_hack_license_number: Optional[str] = None
    vehicle_vin_number: Optional[str] = None

class VehicleInfo(BaseModel):
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_model_year: Optional[str] = None

class AdditionalInfo(BaseModel):
    is_owned_by_self: Optional[bool] = None
    has_named_drivers: Optional[bool] = None
    has_workers_comp: Optional[bool] = None
    does_not_have_workers_comp: Optional[bool] = None
    obtains_fares_via_radio_base: Optional[bool] = None
    affiliated_radio_base: Optional[str] = None

class ApplicationFormData(BaseModel):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    license_info: LicenseInfo = Field(default_factory=LicenseInfo)
    vehicle_info: VehicleInfo = Field(default_factory=VehicleInfo)
    additional_info: AdditionalInfo = Field(default_factory=AdditionalInfo)
    language: str = "en"
    documents: Dict[str, str] = Field(default_factory=dict)
    application_id: str = Field(default_factory=lambda: f"{100000 + hash(str(id(object()))) % 900000}")
    
    def to_dict(self):
        return json.loads(self.json())
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

# Track application state
@cl.cache
def get_application_data():
    if not hasattr(get_application_data, "data"):
        get_application_data.data = ApplicationFormData()
    return get_application_data.data

# Reset application data
def reset_application_data():
    get_application_data.data = ApplicationFormData()
    return get_application_data.data

@cl.cache
def get_current_step():
    if not hasattr(get_current_step, "step"):
        get_current_step.step = "welcome"
    return get_current_step.step

@cl.cache
def set_current_step(step):
    get_current_step.step = step
    return get_current_step.step

# Updated function to get content safely from AskUserMessage response
def get_response_content(response):
    """Safely extract content from AskUserMessage response in Chainlit"""
    if hasattr(response, 'content'):
        return response.content
    elif hasattr(response, 'output'):
        return response.output
    elif isinstance(response, dict):
        if "content" in response:
            return response["content"]
        elif "output" in response:
            return response["output"]
    return ""  # Return empty string as fallback

# Document processing with GPT-4o
async def process_document_with_gpt4o(file_data: bytes, document_type: str) -> Dict[str, Any]:
    try:
        # Prepare base64 encoded image
        base64_image = base64.b64encode(file_data).decode('utf-8')
        
        # Create appropriate prompt based on document type
        if document_type == "nys_license":
            prompt = "Extract the following information from this New York State Driver License: license number, first name, middle name (if present), last name, address, city, state, ZIP code. Return the data in JSON format with these field names: nys_license_number, first_name, middle_name, last_name, address, city, state, zip."
        elif document_type == "tlc_license":
            prompt = "Extract the following information from this TLC Hack License: license number, first name, last name. Return the data in JSON format with these field names: tlc_hack_license_number, first_name, last_name."
        elif document_type == "vehicle_title":
            prompt = "Extract the following information from this Vehicle Certificate of Title: VIN number, vehicle make, vehicle model, vehicle year, owner name. Return the data in JSON format with these field names: vehicle_vin_number, vehicle_make, vehicle_model, vehicle_model_year, owner_name."
        else:
            prompt = "Extract the following information from this Radio Base Certification Letter: radio base name. Return the data in JSON format with field name: affiliated_radio_base."
        
        # Call OpenAI API
        response = await cl.make_async(client.chat.completions.create)(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a document processing assistant. Extract information from the provided image and return it in clean JSON format with no additional text."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
        
    except Exception as e:
        cl.logger.error(f"Error processing document: {str(e)}")
        return {"error": f"Failed to process document: {str(e)}"}

# Update application data with extracted information
def update_application_with_extracted_data(data, document_type):
    app_data = get_application_data()
    
    if document_type == "nys_license":
        app_data.personal_info.first_name = data.get("first_name", app_data.personal_info.first_name)
        app_data.personal_info.middle_name = data.get("middle_name", app_data.personal_info.middle_name)
        app_data.personal_info.last_name = data.get("last_name", app_data.personal_info.last_name)
        app_data.personal_info.address = data.get("address", app_data.personal_info.address)
        app_data.personal_info.city = data.get("city", app_data.personal_info.city)
        app_data.personal_info.state = data.get("state", app_data.personal_info.state)
        app_data.personal_info.zip = data.get("zip", app_data.personal_info.zip)
        app_data.license_info.nys_license_number = data.get("nys_license_number", app_data.license_info.nys_license_number)
    
    elif document_type == "tlc_license":
        app_data.license_info.tlc_hack_license_number = data.get("tlc_hack_license_number", app_data.license_info.tlc_hack_license_number)
    
    elif document_type == "vehicle_title":
        app_data.license_info.vehicle_vin_number = data.get("vehicle_vin_number", app_data.license_info.vehicle_vin_number)
        app_data.vehicle_info.vehicle_make = data.get("vehicle_make", app_data.vehicle_info.vehicle_make)
        app_data.vehicle_info.vehicle_model = data.get("vehicle_model", app_data.vehicle_info.vehicle_model)
        app_data.vehicle_info.vehicle_model_year = data.get("vehicle_model_year", app_data.vehicle_info.vehicle_model_year)
        
        # Check if owner name matches
        owner_name = data.get("owner_name")
        full_name = f"{app_data.personal_info.first_name} {app_data.personal_info.last_name}".strip()
        if owner_name and full_name:
            app_data.additional_info.is_owned_by_self = owner_name.lower() in full_name.lower() or full_name.lower() in owner_name.lower()
    
    elif document_type == "radio_base_cert":
        app_data.additional_info.obtains_fares_via_radio_base = True
        app_data.additional_info.affiliated_radio_base = data.get("affiliated_radio_base", app_data.additional_info.affiliated_radio_base)
    
    return app_data

# Chainlit setup
@cl.on_chat_start
async def start():
    # Initialize application data
    app_data = get_application_data()
    
    # Welcome message
    await cl.Message(content=rio.get("welcome", "en")).send()
    
    # Start the application process
    await start_application()

# Helper function to start the application process
async def start_application():
    app_data = get_application_data()
    
    # Language selection using AskActionMessage
    res = await cl.AskActionMessage(
        content=rio.get("language_selection", "en"),
        actions=[
            cl.Action(name="en", label=rio.get("btn_english", "en"), payload={"language": "English"}),
            cl.Action(name="es", label=rio.get("btn_spanish", "en"), payload={"language": "Spanish"}),
            cl.Action(name="zh", label=rio.get("btn_chinese", "en"), payload={"language": "Chinese"})
        ]
    ).send()
    
    # Process language selection
    if res:
        language_code = res.get("name")
        language_name = res.get("payload").get("language")
        
        # Update language preference
        app_data.language = language_code
        
        # Start with NYS license request
        await request_nys_license()

# Request NYS Driver License
async def request_nys_license():
    set_current_step("nys_license_upload")
    app_data = get_application_data()
    
    # Remove duplicate message - only keep the prompt in AskFileMessage
    files = await cl.AskFileMessage(
        content=rio.get("nys_license_intro", app_data.language),
        accept=["image/jpeg", "image/png", "application/pdf"],
        max_size_mb=5,
        timeout=20000
    ).send()
    
    if files:
        file = files[0]
        await process_uploaded_file(file, "nys_license")

# Request TLC Hack License
async def request_tlc_license():
    set_current_step("tlc_license_upload")
    app_data = get_application_data()
    
    # Remove duplicate message - only keep the prompt in AskFileMessage
    files = await cl.AskFileMessage(
        content=rio.get("tlc_license_intro", app_data.language),
        accept=["image/jpeg", "image/png", "application/pdf"],
        max_size_mb=5,
        timeout=20000
    ).send()
    
    if files:
        file = files[0]
        await process_uploaded_file(file, "tlc_license")

# Request Vehicle Title
async def request_vehicle_title():
    set_current_step("vehicle_title_upload")
    app_data = get_application_data()
    
    # Remove duplicate message - only keep the prompt in AskFileMessage
    files = await cl.AskFileMessage(
        content=rio.get("vehicle_title_intro", app_data.language),
        accept=["image/jpeg", "image/png", "application/pdf"],
        max_size_mb=5,
        timeout=20000
    ).send()
    
    if files:
        file = files[0]
        await process_uploaded_file(file, "vehicle_title")

# Request contact information
async def request_contact_info():
    set_current_step("contact_info")
    app_data = get_application_data()
    
    await cl.Message(
        content=rio.get("contact_info_intro", app_data.language)
    ).send()
    
    phone_msg = await cl.AskUserMessage(content=rio.get("phone_request", app_data.language)).send()
    email_msg = await cl.AskUserMessage(content=rio.get("email_request", app_data.language)).send()
    
    # Update application data
    app_data = get_application_data()
    app_data.personal_info.phone = get_response_content(phone_msg)
    app_data.personal_info.email = get_response_content(email_msg)
    
    # Move to additional questions
    await ask_additional_questions()

# Ask additional questions
async def ask_additional_questions():
    set_current_step("additional_questions")
    app_data = get_application_data()
    
    # Skip ownership question if we already determined it from documents
    if app_data.additional_info.is_owned_by_self is None:
        # Ask if the vehicle is owned by self
        res = await cl.AskActionMessage(
            content=rio.get("owned_by_self", app_data.language),
            actions=[
                cl.Action(name="yes_owned", label=rio.get("btn_confirm", app_data.language), payload={"owned": True}),
                cl.Action(name="no_owned", label=rio.get("btn_edit", app_data.language), payload={"owned": False})
            ]
        ).send()
        
        if res:
            app_data.additional_info.is_owned_by_self = res.get("payload").get("owned")
    
    # Ask about named drivers
    res = await cl.AskActionMessage(
        content=rio.get("named_drivers", app_data.language),
        actions=[
            cl.Action(name="yes_named", label=rio.get("btn_confirm", app_data.language), payload={"named_drivers": True}),
            cl.Action(name="no_named", label=rio.get("btn_edit", app_data.language), payload={"named_drivers": False})
        ]
    ).send()
    
    if res:
        app_data.additional_info.has_named_drivers = res.get("payload").get("named_drivers")
    
    # Ask about workers comp
    res = await cl.AskActionMessage(
        content=rio.get("workers_comp", app_data.language),
        actions=[
            cl.Action(name="yes_workers", label=rio.get("btn_confirm", app_data.language), payload={"workers_comp": True}),
            cl.Action(name="no_workers", label=rio.get("btn_edit", app_data.language), payload={"workers_comp": False})
        ]
    ).send()
    
    if res:
        has_workers_comp = res.get("payload").get("workers_comp")
        app_data.additional_info.has_workers_comp = has_workers_comp
        app_data.additional_info.does_not_have_workers_comp = not has_workers_comp
    
    # Ask about radio base
    res = await cl.AskActionMessage(
        content=rio.get("radio_base", app_data.language),
        actions=[
            cl.Action(name="yes_radio", label=rio.get("btn_confirm", app_data.language), payload={"radio_base": True}),
            cl.Action(name="no_radio", label=rio.get("btn_edit", app_data.language), payload={"radio_base": False})
        ]
    ).send()
    
    if res:
        obtains_fares = res.get("payload").get("radio_base")
        app_data.additional_info.obtains_fares_via_radio_base = obtains_fares
        
        if obtains_fares:
            # Ask for Radio Base name
            res = await cl.AskActionMessage(
                content=rio.get("radio_base_select", app_data.language),
                actions=[
                    cl.Action(name="radio_nyc", label="NYC Yellow Cab", payload={"radio_base_name": "NYC Yellow Cab"}),
                    cl.Action(name="radio_uber", label="Uber", payload={"radio_base_name": "Uber"}),
                    cl.Action(name="radio_lyft", label="Lyft", payload={"radio_base_name": "Lyft"}),
                    cl.Action(name="radio_other", label="Other", payload={"radio_base_name": "Other"})
                ]
            ).send()
            
            if res:
                radio_base_name = res.get("payload").get("radio_base_name")
                app_data.additional_info.affiliated_radio_base = radio_base_name
                
                if radio_base_name == "Other":
                    # Ask for custom radio base name
                    radio_base_msg = await cl.AskUserMessage(content="Please enter the name of your Radio Base:").send()
                    app_data.additional_info.affiliated_radio_base = get_response_content(radio_base_msg)
                
                # Request Radio Base cert if not already uploaded
                if "radio_base_cert" not in app_data.documents:
                    set_current_step("radio_base_cert_upload")
                    
                    files = await cl.AskFileMessage(
                        content=rio.get("radio_base_intro", app_data.language),
                        accept=["image/jpeg", "image/png", "application/pdf"],
                        max_size_mb=5,
                        timeout=20000
                    ).send()
                    
                    if files:
                        file = files[0]
                        await process_uploaded_file(file, "radio_base_cert")
    
    # Move to review
    await show_review_form()

# Process uploaded file
async def process_uploaded_file(file: cl.File, document_type: str):
    app_data = get_application_data()
    
    # Show processing message
    processing_msg = await cl.Message(content=rio.get("processing_document", app_data.language)).send()
    
    # Store file reference
    app_data.documents[document_type] = file.name
    
    try:
        # Read file content
        with open(file.path, "rb") as f:
            file_data = f.read()
        
        # Process with GPT-4o
        extracted_data = await process_document_with_gpt4o(file_data, document_type)
        
        # Update application data
        update_application_with_extracted_data(extracted_data, document_type)
        
        # Update processing message - correct pattern for Chainlit API
        processing_msg.content = rio.get("document_success", app_data.language)
        await processing_msg.update()
        
        # Create dataframe for extracted data
        data = []
        for key, value in extracted_data.items():
            if key != "error" and value:
                formatted_key = key.replace("_", " ").title()
                data.append({"Field": formatted_key, "Extracted Value": value})
        
        df = pd.DataFrame(data)
        
        # Send extracted data message with confirmation buttons
        await cl.Message(
            content=rio.get("vehicle_title_review", app_data.language),
            elements=[cl.Dataframe(data=df, name="extracted_data")]
        ).send()
        
        res = await cl.AskActionMessage(
            content="",
            actions=[
                cl.Action(name="confirm_data", label=rio.get("btn_confirm", app_data.language), payload={"document_type": document_type}),
                cl.Action(name="edit_data", label=rio.get("btn_edit", app_data.language), payload={"document_type": document_type})
            ]
        ).send()
        
        if res:
            action_name = res.get("name")
            document_type = res.get("payload").get("document_type")
            
            if action_name == "confirm_data":
                # Handle confirmation
                if document_type == "nys_license":
                    await cl.Message(content=rio.get("nys_license_confirm", app_data.language)).send()
                    await request_tlc_license()
                elif document_type == "tlc_license":
                    await cl.Message(content=rio.get("tlc_license_confirm", app_data.language)).send()
                    await request_vehicle_title()
                elif document_type == "vehicle_title":
                    await cl.Message(content=rio.get("vehicle_title_confirm", app_data.language)).send()
                    await request_contact_info()
                elif document_type == "radio_base_cert":
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await show_review_form()
            
            elif action_name == "edit_data":
                # Handle edit
                await cl.Message(content="Let's edit the extracted information:").send()
                
                if document_type == "nys_license":
                    # Send form for NYS license data
                    license_num_response = await cl.AskUserMessage(
                        content=f"NYS License Number: (Current: {app_data.license_info.nys_license_number or 'None'})"
                    ).send()
                    
                    first_name_response = await cl.AskUserMessage(
                        content=f"First Name: (Current: {app_data.personal_info.first_name or 'None'})"
                    ).send()
                    
                    last_name_response = await cl.AskUserMessage(
                        content=f"Last Name: (Current: {app_data.personal_info.last_name or 'None'})"
                    ).send()
                    
                    address_response = await cl.AskUserMessage(
                        content=f"Address: (Current: {app_data.personal_info.address or 'None'})"
                    ).send()
                    
                    # Update data
                    app_data.license_info.nys_license_number = get_response_content(license_num_response)
                    app_data.personal_info.first_name = get_response_content(first_name_response)
                    app_data.personal_info.last_name = get_response_content(last_name_response)
                    app_data.personal_info.address = get_response_content(address_response)
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await request_tlc_license()
                
                elif document_type == "tlc_license":
                    # Handle TLC License manual entry
                    tlc_license_response = await cl.AskUserMessage(
                        content="TLC License Number:"
                    ).send()
                    
                    # Update data
                    app_data.license_info.tlc_hack_license_number = get_response_content(tlc_license_response)
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await request_vehicle_title()
                
                elif document_type == "vehicle_title":
                    # Handle Vehicle Title manual entry
                    vin_response = await cl.AskUserMessage(
                        content="Vehicle VIN Number:"
                    ).send()
                    
                    make_response = await cl.AskUserMessage(
                        content="Vehicle Make:"
                    ).send()
                    
                    model_response = await cl.AskUserMessage(
                        content="Vehicle Model:"
                    ).send()
                    
                    year_response = await cl.AskUserMessage(
                        content="Vehicle Year:"
                    ).send()
                    
                    # Update data
                    app_data.license_info.vehicle_vin_number = get_response_content(vin_response)
                    app_data.vehicle_info.vehicle_make = get_response_content(make_response)
                    app_data.vehicle_info.vehicle_model = get_response_content(model_response)
                    app_data.vehicle_info.vehicle_model_year = get_response_content(year_response)
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await request_contact_info()
                
                elif document_type == "radio_base_cert":
                    # Handle Radio Base Certificate manual entry
                    radio_base_response = await cl.AskUserMessage(
                        content="Radio Base Name:"
                    ).send()
                    
                    # Update data
                    app_data.additional_info.affiliated_radio_base = get_response_content(radio_base_response)
                    app_data.additional_info.obtains_fares_via_radio_base = True
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await show_review_form()
        
    except Exception as e:
        cl.logger.error(f"Error processing file: {str(e)}")
        # Update processing message - correct pattern for Chainlit API
        processing_msg.content = rio.get("document_error", app_data.language) + f": {str(e)}"
        await processing_msg.update()
        
        # Ask to try again using AskActionMessage
        res = await cl.AskActionMessage(
            content=rio.get("document_error", app_data.language),
            actions=[
                cl.Action(name="retry_upload", label=rio.get("btn_retry", app_data.language), payload={"document_type": document_type}),
                cl.Action(name="manual_entry", label=rio.get("btn_manual", app_data.language), payload={"document_type": document_type})
            ]
        ).send()
        
        if res:
            action_name = res.get("name")
            document_type = res.get("payload").get("document_type")
            
            if action_name == "retry_upload":
                if document_type == "nys_license":
                    await request_nys_license()
                elif document_type == "tlc_license":
                    await request_tlc_license()
                elif document_type == "vehicle_title":
                    await request_vehicle_title()
                else:  # radio_base_cert
                    set_current_step("radio_base_cert_upload")
                    await cl.Message(content=rio.get("radio_base_intro", app_data.language)).send()
                    
                    files = await cl.AskFileMessage(
                        content=rio.get("radio_base_intro", app_data.language),
                        accept=["image/jpeg", "image/png", "application/pdf"],
                        max_size_mb=5,
                        timeout=20000
                    ).send()
                    
                    if files:
                        file = files[0]
                        await process_uploaded_file(file, "radio_base_cert")
            
            elif action_name == "manual_entry":
                # Handle manual entry for different document types
                await cl.Message(content="Let's enter the information manually:").send()
                
                if document_type == "nys_license":
                    # Send form for NYS license data
                    license_num_response = await cl.AskUserMessage(
                        content="NYS License Number:"
                    ).send()
                    
                    first_name_response = await cl.AskUserMessage(
                        content="First Name:"
                    ).send()
                    
                    last_name_response = await cl.AskUserMessage(
                        content="Last Name:"
                    ).send()
                    
                    address_response = await cl.AskUserMessage(
                        content="Address:"
                    ).send()
                    
                    # Update data
                    app_data.license_info.nys_license_number = get_response_content(license_num_response)
                    app_data.personal_info.first_name = get_response_content(first_name_response)
                    app_data.personal_info.last_name = get_response_content(last_name_response)
                    app_data.personal_info.address = get_response_content(address_response)
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await request_tlc_license()
                
                elif document_type == "tlc_license":
                    # Handle TLC License manual entry
                    tlc_license_response = await cl.AskUserMessage(
                        content="TLC License Number:"
                    ).send()
                    
                    # Update data
                    app_data.license_info.tlc_hack_license_number = get_response_content(tlc_license_response)
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await request_vehicle_title()
                
                elif document_type == "vehicle_title":
                    # Handle Vehicle Title manual entry
                    vin_response = await cl.AskUserMessage(
                        content="Vehicle VIN Number:"
                    ).send()
                    
                    make_response = await cl.AskUserMessage(
                        content="Vehicle Make:"
                    ).send()
                    
                    model_response = await cl.AskUserMessage(
                        content="Vehicle Model:"
                    ).send()
                    
                    year_response = await cl.AskUserMessage(
                        content="Vehicle Year:"
                    ).send()
                    
                    # Update data
                    app_data.license_info.vehicle_vin_number = get_response_content(vin_response)
                    app_data.vehicle_info.vehicle_make = get_response_content(make_response)
                    app_data.vehicle_info.vehicle_model = get_response_content(model_response)
                    app_data.vehicle_info.vehicle_model_year = get_response_content(year_response)
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await request_contact_info()
                
                elif document_type == "radio_base_cert":
                    # Handle Radio Base Certificate manual entry
                    radio_base_response = await cl.AskUserMessage(
                        content="Radio Base Name:"
                    ).send()
                    
                    # Update data
                    app_data.additional_info.affiliated_radio_base = get_response_content(radio_base_response)
                    app_data.additional_info.obtains_fares_via_radio_base = True
                    
                    # Continue
                    await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                    await show_review_form()
            else:
                await cl.Message(content=rio.get("invalid_option", app_data.language)).send()
                await show_review_form()

# Show review form
async def show_review_form():
    """Show review form with all collected data"""
    app_data = get_application_data()
    set_current_step("review")
    
    # Create formatted display of all collected information
    await cl.Message(content=f"## {rio.get('review_intro', app_data.language)}").send()
    
    # Format personal information
    personal_info = [
        {"Field": "First Name", "Value": app_data.personal_info.first_name},
        {"Field": "Last Name", "Value": app_data.personal_info.last_name},
        {"Field": "Address", "Value": app_data.personal_info.address},
        {"Field": "Email", "Value": app_data.personal_info.email},
        {"Field": "Phone", "Value": app_data.personal_info.phone},
    ]
    
    # Format license information
    license_info = [
        {"Field": "NYS License Number", "Value": app_data.license_info.nys_license_number},
        {"Field": "TLC License Number", "Value": app_data.license_info.tlc_hack_license_number},
        {"Field": "Vehicle VIN Number", "Value": app_data.license_info.vehicle_vin_number},
        {"Field": "Radio Base", "Value": app_data.additional_info.affiliated_radio_base},
    ]
    
    # Format uploaded documents
    documents = [
        {"Field": "NYS Driver License", "Value": app_data.documents.get("nys_license", "Not uploaded")},
        {"Field": "TLC Hack License", "Value": app_data.documents.get("tlc_license", "Not uploaded")},
        {"Field": "Vehicle Title", "Value": app_data.documents.get("vehicle_title", "Not uploaded")},
        {"Field": "Radio Base Certificate", "Value": app_data.documents.get("radio_base_cert", "Not uploaded")},
    ]
    
    # Create DataFrames for each section
    personal_df = pd.DataFrame(personal_info)
    license_df = pd.DataFrame(license_info)
    documents_df = pd.DataFrame(documents)
    
    # Send each section with appropriate title
    await cl.Message(content="### Personal Information", elements=[
        cl.Dataframe(data=personal_df, name="personal_info")
    ]).send()
    
    await cl.Message(content="### License Information", elements=[
        cl.Dataframe(data=license_df, name="license_info")
    ]).send()
    
    await cl.Message(content="### Uploaded Documents", elements=[
        cl.Dataframe(data=documents_df, name="documents")
    ]).send()
    
    # Ask for confirmation using AskActionMessage
    res = await cl.AskActionMessage(
        content=rio.get("confirm_question", app_data.language),
        actions=[
            cl.Action(name="submit_application", label=rio.get("btn_submit", app_data.language), payload={}),
            cl.Action(name="edit_data", label=rio.get("btn_edit_info", app_data.language), payload={})
        ]
    ).send()
    
    if res:
        action_name = res.get("name")
        
        if action_name == "submit_application":
            # Show submission confirmation
            processing_msg = await cl.Message(content=rio.get("processing", app_data.language)).send()
            
            # Simulate processing delay
            import asyncio
            await asyncio.sleep(2)
            
            # Update message with confirmation - correct pattern for Chainlit API
            processing_msg.content = rio.get("submission_success", app_data.language)
            await processing_msg.update()
            
            # Provide confirmation number and next steps
            await cl.Message(content=f"""
{rio.get("submission_details", app_data.language)}

**{rio.get("confirmation_number", app_data.language)}{app_data.application_id}**
            """).send()
            
            # Offer to start a new application or exit
            res = await cl.AskActionMessage(
                content=rio.get("confirm_question", app_data.language),
                actions=[
                    cl.Action(name="new_application", label=rio.get("new_application", app_data.language), payload={}),
                    cl.Action(name="exit_app", label=rio.get("exit", app_data.language), payload={})
                ]
            ).send()
            
            if res:
                action_name = res.get("name")
                
                if action_name == "new_application":
                    # Reset application data
                    reset_application_data()
                    # Start new application
                    await cl.Message(content=rio.get("restart", app_data.language)).send()
                    await start()
                    
                elif action_name == "exit_app":
                    # Show exit message
                    await cl.Message(content="""
Thank you for using our Commercial Auto Insurance Application Assistant.
If you have any questions, please contact our support team at support@insurance.com.
                    """).send()
        
        elif action_name == "edit_data":
            # Allow user to select what to edit
            await cl.Message(content=rio.get("edit_option", app_data.language)).send()
            
            edit_option = await cl.AskUserMessage(
                content="""
Please select what you'd like to edit:
1. Personal Information
2. License Information
3. Uploaded Documents

Enter the number of your choice:
                """
            ).send()
            
            # Access the response value correctly
            choice = get_response_content(edit_option)
            
            if choice == "1":
                # Edit personal information
                await cl.Message(content="Let's update your personal information:").send()
                
                # Get updated information
                first_name_response = await cl.AskUserMessage(
                    content=f"First Name: (Current: {app_data.personal_info.first_name or 'None'})"
                ).send()
                
                last_name_response = await cl.AskUserMessage(
                    content=f"Last Name: (Current: {app_data.personal_info.last_name or 'None'})"
                ).send()
                
                address_response = await cl.AskUserMessage(
                    content=f"Address: (Current: {app_data.personal_info.address or 'None'})"
                ).send()
                
                email_response = await cl.AskUserMessage(
                    content=f"Email: (Current: {app_data.personal_info.email or 'None'})"
                ).send()
                
                phone_response = await cl.AskUserMessage(
                    content=f"Phone: (Current: {app_data.personal_info.phone or 'None'})"
                ).send()
                
                # Update data
                app_data.personal_info.first_name = get_response_content(first_name_response)
                app_data.personal_info.last_name = get_response_content(last_name_response)
                app_data.personal_info.address = get_response_content(address_response)
                app_data.personal_info.email = get_response_content(email_response)
                app_data.personal_info.phone = get_response_content(phone_response)
                
                # Show updated review
                await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                await show_review_form()
                
            elif choice == "2":
                # Edit license information
                await cl.Message(content="Let's update your license information:").send()
                
                # Get updated information
                nys_license_response = await cl.AskUserMessage(
                    content=f"NYS License Number: (Current: {app_data.license_info.nys_license_number or 'None'})"
                ).send()
                
                tlc_license_response = await cl.AskUserMessage(
                    content=f"TLC License Number: (Current: {app_data.license_info.tlc_hack_license_number or 'None'})"
                ).send()
                
                vehicle_title_response = await cl.AskUserMessage(
                    content=f"Vehicle VIN Number: (Current: {app_data.license_info.vehicle_vin_number or 'None'})"
                ).send()
                
                radio_base_response = await cl.AskUserMessage(
                    content=f"Radio Base: (Current: {app_data.additional_info.affiliated_radio_base or 'None'})"
                ).send()
                
                # Update data
                app_data.license_info.nys_license_number = get_response_content(nys_license_response)
                app_data.license_info.tlc_hack_license_number = get_response_content(tlc_license_response)
                app_data.license_info.vehicle_vin_number = get_response_content(vehicle_title_response)
                app_data.additional_info.affiliated_radio_base = get_response_content(radio_base_response)
                
                # Show updated review
                await cl.Message(content=rio.get("information_updated", app_data.language)).send()
                await show_review_form()
                
            elif choice == "3":
                # Edit uploaded documents
                await cl.Message(content="Which document would you like to reupload?").send()
                
                doc_option = await cl.AskUserMessage(
                    content="""
Please select which document to reupload:
1. NYS Driver License
2. TLC Hack License
3. Vehicle Title
4. Radio Base Certificate

Enter the number of your choice:
                    """
                ).send()
                
                doc_choice = get_response_content(doc_option).strip()
                
                if doc_choice == "1":
                    await request_nys_license()
                elif doc_choice == "2":
                    await request_tlc_license()
                elif doc_choice == "3":
                    await request_vehicle_title()
                elif doc_choice == "4":
                    set_current_step("radio_base_cert_upload")
                    
                    files = await cl.AskFileMessage(
                        content=rio.get("radio_base_intro", app_data.language),
                        accept=["image/jpeg", "image/png", "application/pdf"],
                        max_size_mb=5,
                        timeout=20000
                    ).send()
                    
                    if files:
                        file = files[0]
                        await process_uploaded_file(file, "radio_base_cert")
                else:
                    await cl.Message(content=rio.get("invalid_option", app_data.language)).send()
                    await show_review_form()
            else:
                await cl.Message(content=rio.get("invalid_option", app_data.language)).send()
                await show_review_form()

# Handle regular text messages
@cl.on_message
async def on_message(message: cl.Message):
    """Handle regular text messages from the user"""
    app_data = get_application_data()
    
    # Get user text input
    user_input = message.content.lower()
    
    # Handle restart command
    if "restart" in user_input or "start over" in user_input or "new application" in user_input:
        # Reset application data
        reset_application_data()
        # Start new application
        await cl.Message(content=rio.get("restart", app_data.language)).send()
        await start_application()
        return
    
    # Handle review command
    if "review" in user_input or "show review" in user_input or "check application" in user_input:
        # Show review form
        await cl.Message(content=rio.get("review_intro", app_data.language)).send()
        await show_review_form()
        return
    
    # Default response
    await cl.Message(content=f"""
{rio.get("welcome", app_data.language)}

{rio.get("restart", app_data.language)}
    """).send()
    
    # If no application in progress, start one
    if not any([
        get_application_data().personal_info.first_name,
        get_application_data().license_info.nys_license_number,
        get_application_data().documents
    ]):
        await start_application()

# Requirements.txt
"""
chainlit==1.0.0
openai==1.20.0
pydantic==2.6.0
python-dotenv==1.0.0
httpx>=0.20.0
pandas>=1.3.0
"""

# .env.example
"""
OPENAI_API_KEY=your_openai_api_key_here
"""

# Run with: chainlit run app.py -w