import os
import json
import re
import time
import builtins
from functools import wraps
import ollama

# # Attempt to load OpenAI, but don't crash the Django server if it isn't installed
# try:
#     from openai import OpenAI
#     OPENAI_AVAILABLE = True
# except ImportError:
#     OPENAI_AVAILABLE = False

def patch_windows_console_emojis():
    """Fixes the Errno 22 crash when printing emojis in the Windows console."""
    _original_print = builtins.print

    def safe_print(*args, **kwargs):
        try:
            _original_print(*args, **kwargs)
        except OSError:
            safe_args = [str(arg).encode('ascii', 'replace').decode('ascii') for arg in args]
            _original_print(*safe_args, **kwargs)

    builtins.print = safe_print

def extract_json_from_text(text):
    """Robust JSON extraction that handles nested markdown and literal newlines."""
    import json
    
    match = re.search(r'```json\s*(.*)\s*```', text, re.DOTALL)
    if match: 
        try: return json.loads(match.group(1), strict=False)
        except: pass
        
    match_obj = re.search(r'(\{.*\})', text, re.DOTALL)
    if match_obj: 
        try: return json.loads(match_obj.group(1), strict=False)
        except: pass
        
    match_arr = re.search(r'(\[.*\])', text, re.DOTALL)
    if match_arr:
        try: return json.loads(match_arr.group(1), strict=False)
        except: pass
        
    return None

def get_spelling_instruction(locale):
    """Returns the system prompt instruction for spelling AND cultural tone based on locale."""
    if locale.lower() == 'uk':
        return "You MUST use British English spelling (e.g., optimise, Prioritise, centre, categorise). TONE: Highly pragmatic, understated, and focused on clean architecture, security, and exact technical ROI."
    elif locale.lower() == 'us':
        return "You MUST use American English spelling (e.g., optimize, prioritize , center, categorize). TONE: Visionary, enthusiastic, and focused on massive scale, disruption, 10x productivity, and shipping fast."
    else:
        return "You MUST use British English spelling."

def retry_llm_call(max_retries=3, delay=1, fallback=None):
    """
    Standard Function Decorator: Retries the entire python function block.
    Acts as the final failsafe against network disconnects or complete system timeouts.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        return result
                except Exception as e:
                    pass 
                time.sleep(delay)
            return fallback
        return wrapper
    return decorator


# # ==========================================
# # ENTERPRISE HYBRID ROUTER
# # ==========================================
# def hybrid_chat(model_name, messages, format_type='json', options=None, local_retries=2):
#     """
#     The Hybrid Cloud Fallback Router.
#     Tries local Ollama first. If it returns invalid data or truncates the array,
#     it seamlessly routes the exact same prompt to OpenAI for a rescue operation.
#     """
#     temperature = options.get('temperature', 0.7) if options else 0.7
#     num_predict = options.get('num_predict', 3000) if options else 3000

#     # 1. Attempt Local Ollama Call multiple times before spending money
#     for attempt in range(local_retries):
#         try:
#             response = ollama.chat(
#                 model=model_name, 
#                 messages=messages, 
#                 format=format_type, 
#                 options=options
#             )
            
#             # Extract content to verify it didn't completely hallucinate
#             content = response.get('message', {}).get('content', '')
            
#             # If we expect JSON, ensure the local model actually returned parseable JSON
#             if format_type == 'json' and not extract_json_from_text(content):
#                 raise ValueError("Local LLM truncated the array or returned malformed JSON.")
                
#             return response
            
#         except Exception as e:
#             print(f"      ⚠️  [ROUTER] Local attempt {attempt + 1}/{local_retries} failed: {e}")
#             time.sleep(1)

#     # 2. LOCAL FAILED. Route to Cloud API Rescue!
#     print("      🚀 [ROUTER] Local model exhausted. Engaging OpenAI (gpt-4o-mini) Rescue...")
    
#     if not OPENAI_AVAILABLE:
#         print("      ❌ [ROUTER] OpenAI library not installed. Run: pip install openai")
#         raise RuntimeError("OpenAI fallback failed (Not installed).")

#     openai_api_key = os.environ.get("OPENAI_API_KEY")
#     if not openai_api_key:
#         print("      ❌ [ROUTER] OPENAI_API_KEY environment variable not set in .env")
#         raise RuntimeError("OpenAI fallback failed (No API Key).")

#     try:
#         client = OpenAI(api_key=openai_api_key)
        
#         # OpenAI requires a slightly different keyword structure for JSON enforcement
#         completion_kwargs = {
#             "model": "gpt-4o-mini",
#             "messages": messages,
#             "temperature": temperature,
#             "max_tokens": num_predict,
#         }
        
#         if format_type == 'json':
#             completion_kwargs["response_format"] = {"type": "json_object"}
        
#         response = client.chat.completions.create(**completion_kwargs)
#         cloud_content = response.choices[0].message.content
        
#         print("      ✅ [ROUTER] OpenAI Rescue Successful!")
        
#         # Format the OpenAI response to perfectly mimic Ollama's dictionary structure!
#         # This ensures your generator scripts don't need to change how they parse the data.
#         return {
#             'message': {
#                 'content': cloud_content
#             }
#         }
        
#     except Exception as e:
#         print(f"      ❌ [ROUTER] OpenAI Rescue Failed: {e}")
#         raise e
    

def log_warning(domain_name, message):
    """Logs non-critical LLM warnings and fallbacks to a centralized file."""
    from django.conf import settings
    warning_log_file = os.path.join(settings.BASE_DIR, 'data_import', 'generation_warnings_log.txt')
    
    print(f"           ⚠️  [WARNING]: {message}")
    
    os.makedirs(os.path.dirname(warning_log_file), exist_ok=True)
    with open(warning_log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{domain_name.upper()}] {message}\n")
