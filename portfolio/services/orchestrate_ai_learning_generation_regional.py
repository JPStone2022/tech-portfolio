import os
import sys
import django
import argparse
import json
import re
import ollama
import itertools
import random
import time
import urllib.parse
from django.utils.text import slugify

from functools import wraps
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

# --- SETUP ---
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from ai_concepts.models import AILearningPath, AIPathWeek, AIPathDay
# from shop.models import Product as ShopProduct
# from affiliates.models import AffiliateProduct, ProductVariant, Merchant, AffiliateCategory

# --- FIX FOR WINDOWS CONSOLE EMOJI CRASH (Errno 22) ---
import builtins
_original_print = builtins.print

def safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except OSError:
        safe_args = [str(arg).encode('ascii', 'replace').decode('ascii') for arg in args]
        _original_print(*safe_args, **kwargs)

builtins.print = safe_print
# ------------------------------------------------------

def log_warning(domain_name, message):
    """Logs non-critical LLM warnings and fallbacks to a centralized file."""
    from django.conf import settings
    warning_log_file = os.path.join(settings.BASE_DIR, 'data_import', 'generation_warnings_log.txt')
    
    print(f"           ⚠️  [WARNING]: {message}")
    
    os.makedirs(os.path.dirname(warning_log_file), exist_ok=True)
    with open(warning_log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{domain_name.upper()}] {message}\n")

# --- ADVANCED PYTHON: ENTERPRISE DATACLASSES ---
@dataclass
class AILessonPlan:
    """
    A strict contract for what an AI Lesson Day MUST contain.
    Provides full IDE autocomplete and immunity to KeyErrors during database insertion.
    """
    title: str
    is_rest_day: bool
    theory_lesson: str
    practical_exercise: str
    real_world_case_study: str
    mindset_focus: str

    @classmethod
    def from_dict(cls, data: dict, fallback_title: str, is_rest: bool) -> 'AILessonPlan':
        if not data or not isinstance(data, dict):
            return cls(
                title=fallback_title,
                is_rest_day=is_rest,
                theory_lesson="Theory unavailable. Review documentation.",
                practical_exercise="No practical today.",
                real_world_case_study="N/A",
                mindset_focus="Consolidate concepts."
            )
            
        return cls(
            title=data.get('title', fallback_title),
            is_rest_day=data.get('is_rest_day', is_rest),
            theory_lesson=str(data.get('theory_lesson', 'Theory unavailable.')),
            practical_exercise=str(data.get('practical_exercise', 'No practical today.')),
            real_world_case_study=str(data.get('real_world_case_study', 'N/A')),
            mindset_focus=str(data.get('mindset_focus', 'Stay focused.'))
        )

# --- ADVANCED PYTHON: CUSTOM DECORATOR ---
def retry_llm_call(max_retries=3, delay=1, fallback=None):
    """
    Advanced Python Decorator: Handles LLM retries, JSON parsing failures, 
    and graceful fallbacks without cluttering the core business logic.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        return result
                except Exception:
                    pass 
                time.sleep(delay)
            return fallback
        return wrapper
    return decorator
# -----------------------------------------

MODEL_NAME = "llama3:latest"

# --- AI PERSONA ATTRIBUTES ---
EXPERIENCE_LEVELS = [
    'complete beginner to AI', 
    'business executive / founder', 
    'junior developer upskilling'
]

AI_TOPICS = [
    'Generative AI & Large Language Models (LLMs)', 
    'AI Agents & Workflow Automation', 
    'Computer Vision & Image Generation', 
    'Machine Learning & Predictive Analytics'
]

GOALS = [
    'understanding the landscape to avoid falling behind', 
    'automating daily business tasks', 
    'building an AI-powered MVP', 
    'integrating AI into existing software',
    'Building a Custom AI Coach with RAG',
    'Local AI Deployment with Python & Ollama',
    'Automating Client Onboarding with AI Agents',
]

TIME_AVAILABLE = [
    '15 minutes a day', 
    '1 hour a day', 
    'deep dive',
    'weekend sprints'
]

ANTI_AI_PROMPT = """
CRITICAL: Do NOT use common AI buzzwords or flowery language. 
BANNED WORDS: delve, testament, beacon, bustling, realm, tapestry, moreover, furthermore, inherently, landscape, embark, elevate, unleash, game-changer.
Write like an elite, highly technical Silicon Valley engineer, CTO, or AI Researcher. Be concise, authoritative, and practical.
"""

def is_valid_ai_combination(exp, topic, goal, time_avail):
    """Hardcoded strict filter to ban obvious illogical combinations."""
    if exp in ['business executive / founder', 'complete beginner to AI'] and goal == 'integrating AI into existing software':
        return False
    if time_avail == '15 minutes a day' and goal == 'building an AI-powered MVP':
        return False
    return True

def extract_json_from_text(text):
    """Robust JSON extraction that handles nested code blocks and literal newlines."""
    import json
    
    # Use greedy match (.* instead of .*?) to prevent stopping at nested python code blocks
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
        return "You MUST use British English spelling (e.g., optimise, centre, categorise). TONE: Highly pragmatic, understated, and focused on security, governance, and exact ROI."
    elif locale.lower() == 'us':
        return "You MUST use American English spelling (e.g., optimize, center, categorize). TONE: Visionary, enthusiastic, and focused on massive scale, disruption, and 10x productivity."
    else:
        return "You MUST use British English spelling."

# ==========================================
# STEP 0: AI GATEKEEPER
# ==========================================
@retry_llm_call(max_retries=2, delay=1, fallback=(True, "Failsafe bypass."))
def evaluate_persona_viability(persona_string: str) -> Tuple[bool, str]:
    system_prompt = "You are a pragmatic Tech Lead and EdTech Product Manager. Output ONLY valid JSON."
    user_prompt = f"""
    Task: Evaluate if the following client persona makes logical, practical, and commercial sense for a 4-week AI Learning Path.
    Persona: "{persona_string}"
    Consider:
    1. Does the experience level align with the goal? (e.g., "Complete beginner" cannot realistically achieve "Integrating AI into existing software").
    2. Is the time commitment completely contradictory to the goal?

    Output a JSON object:
    {{
        "is_viable": true or false,
        "reason": "A 1-sentence explanation of why it is viable or exactly why it is a contradiction."
    }}
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.1, 'num_predict': 150})
    data = extract_json_from_text(response['message']['content'])
    if data and isinstance(data, dict) and 'is_viable' in data:
        return data['is_viable'], data.get('reason', '')
    return None

# ==========================================
# STEP 1: GENERATE THE BASE CONCEPT
# ==========================================
@retry_llm_call(max_retries=3, delay=1)
def generate_base_concept(client_persona: str, total_weeks: int = 4, locale: str = 'uk') -> Optional[Dict[str, Any]]:
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are an Elite AI Researcher and Tech Educator. {spelling} {ANTI_AI_PROMPT} Output ONLY valid JSON."
    
    user_prompt = f"""
    Task: Design the core architecture for a {total_weeks}-week AI Learning Path.
    
    Rules:
    1. Output a FLAT JSON dictionary.
    2. 'base_title': A highly marketable, professional name.
    3. 'target_audience': Summarize the target demographic.
    4. CRITICAL RULE: 'weekly_modules' MUST be an array containing EXACTLY {total_weeks} items. You must generate exactly {total_weeks} weeks of content, no more, no less.
    
    --- ACTUAL TASK ---
    Profile: "{client_persona}"
    
    --- EXPECTED OUTPUT FORMAT ---
    {{
        "base_title": "The Executive AI Automation Playbook",
        "target_audience": "Business Executives",
        "weekly_modules": [
            {{"week_number": 1, "title": "Week 1: The Landscape", "focus": "Understanding AI capabilities"}},
            {{"week_number": 2, "title": "Week 2: Implementation", "focus": "Deploying first workflows"}},
            {{"week_number": 3, "title": "Week 3: Automation", "focus": "Connecting agents"}},
            {{"week_number": 4, "title": "Week 4: Scaling", "focus": "Enterprise deployment"}}
        ]
    }}
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.7})
    data = extract_json_from_text(response['message']['content'])
    if data and isinstance(data, dict) and 'weekly_modules' in data and isinstance(data['weekly_modules'], list): 
        return data
    return None

# ==========================================
# STEP 2: TIERED MARKETING COPY
# ==========================================
@retry_llm_call(max_retries=3, delay=1)
def generate_tier_marketing(base_title: str, client_persona: str, tier: str, locale: str = 'uk') -> Optional[Dict[str, Any]]:
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are an elite Tech Copywriter. {spelling} {ANTI_AI_PROMPT} Output ONLY valid JSON."
    
    tier_rules = {
        "Basic": "BASIC TIER: Emphasize that this is an accessible primer. Focus on high-level understanding and basic definitions.",
        "Standard": "STANDARD TIER: Emphasize practical application, solid ROI, and comprehensive tutorials.",
        "Premium": "PREMIUM TIER: Pitch this as an elite tech package. Emphasize underlying architectures, advanced API use-cases, prompt engineering frameworks (e.g., Few-Shot, ReAct), and enterprise-level ROI potential. Tone is authoritative."
    }

    user_prompt = f"""
    Task: Write the marketing copy for the '{tier}' tier of the course "{base_title}".
    CRITICAL TIER RULE: {tier_rules[tier]}
    
    Rules:
    1. Output a FLAT JSON dictionary.
    2. 'variant_name': Name including the tier.
    3. 'description': Short 2-sentence summary.
    4. 'long_description': The main pitch tailored perfectly to the tier.
    5. 'industry_impact': A brief, confident explanation of the real-world impact of this tech scaled to the tier.
    6. 'shop_description': E-commerce checkout pitch.
    7. 'seo_title' and 'meta_description': Tailored to the tier.
    8. 'recommended_equipment_name': A specific technical book or software subscription (Optional).
    9. 'equipment_pitch': A 1-sentence pitch on why this recommended equipment helps.
    
    --- ACTUAL TASK ---
    Base Title: "{base_title}"
    Profile: "{client_persona}"
    Tier: "{tier}"
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.7})
    data = extract_json_from_text(response['message']['content'])
    if data and isinstance(data, dict) and 'variant_name' in data: return data
    return None

# ==========================================
# STEP 3: OPTION 1 - CURRICULUM BOARD AUDIT
# ==========================================
@retry_llm_call(max_retries=3, delay=1)
def generate_premium_weekly_skeleton(base_title: str, week_title: str, week_focus: str, client_persona: str, locale: str = 'uk') -> Optional[Dict[str, Any]]:
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are a Principal AI Architect. {ANTI_AI_PROMPT} {spelling} Output ONLY valid JSON."
    user_prompt = f"""
    Task: Design the UNIQUE 7-day curriculum for "{week_title}" of the "{base_title}" program.
    Focus: {week_focus}
    Profile: {client_persona}

    Rules:
    1. Output a JSON object with a 'days' array containing EXACTLY 7 items (for Monday to Sunday).
    2. EVERY SINGLE DAY MUST BE UNIQUE and progress logically. Do not output a repeating day pattern.
    3. Provide 5-6 elite rigorous study days and 1-2 cognitive rest/consolidation days.

    --- EXPECTED FORMAT ---
    {{
        "days": [
            {{"day_number": 1, "title": "Architectural Overview & Math", "is_rest_day": false}},
            {{"day_number": 2, "title": "API Implementation & Rate Limits", "is_rest_day": false}},
            {{"day_number": 3, "title": "Advanced Prompt Engineering (ReAct)", "is_rest_day": false}},
            {{"day_number": 4, "title": "Consolidation & Cognitive Rest", "is_rest_day": true}},
            {{"day_number": 5, "title": "Vector Databases & Embeddings", "is_rest_day": false}},
            {{"day_number": 6, "title": "RAG Implementation", "is_rest_day": false}},
            {{"day_number": 7, "title": "Weekly Review & Rest", "is_rest_day": true}}
        ]
    }}
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.6})
    data = extract_json_from_text(response['message']['content'])
    if data and isinstance(data, dict) and 'days' in data and isinstance(data['days'], list): return data
    return None

@retry_llm_call(max_retries=4, delay=2)
def audit_full_program_syllabus(raw_syllabus: List[Dict[str, Any]], base_title: str, client_persona: str, locale: str = 'uk') -> Optional[List[Dict[str, Any]]]:
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are the Head of AI Curriculum at an Elite Tech Academy. {ANTI_AI_PROMPT} {spelling} Output ONLY valid JSON."
    
    user_prompt = f"""
    Task: Review this complete {len(raw_syllabus)}-week curriculum skeleton for the "{base_title}" AI course.
    Profile: {client_persona}

    --- CURRENT SYLLABUS DRAFT ---
    {json.dumps(raw_syllabus, indent=2)}

    --- CRITIQUE & REWRITE RULES ---
    1. Repetition Check: Are there repetitive day titles across different weeks? Fix them to ensure distinct, unique concepts.
    2. Progression: Does the technical difficulty curve make sense across the whole month? Adjust day titles so they clearly build on each other.
    3. CRITICAL OUTPUT FORMAT: You MUST return the completely rewritten syllabus wrapped in a JSON object under the key "syllabus". Do NOT change the 'week_title' keys.
    
    --- EXPECTED JSON FORMAT ---
    {{
        "syllabus": [
            {{
                "week_title": "Week 1",
                "days": [
                    {{"day_number": 1, "title": "Day 1 Title", "is_rest_day": false}},
                    {{"day_number": 2, "title": "Day 2 Title", "is_rest_day": false}}
                ]
            }},
            {{
                "week_title": "Week 2",
                "days": [
                    {{"day_number": 1, "title": "Day 1 Title", "is_rest_day": false}},
                    {{"day_number": 2, "title": "Day 2 Title", "is_rest_day": false}}
                ]
            }}
        ]
    }}

    CRITICAL: YOU MUST RETURN ALL WEEKS AND ALL DAYS. DO NOT TRUNCATE THE ARRAYS. DO NOT ADD COMMENTS.
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.3, 'num_predict': 4000})
    data = extract_json_from_text(response['message']['content'])
    
    if data and isinstance(data, dict) and 'syllabus' in data and isinstance(data['syllabus'], list) and len(data['syllabus']) > 0:
        return data['syllabus']
    return None

def compile_and_audit_syllabus(base_title: str, weekly_modules: list, client_persona: str, locale: str = 'uk') -> List[Dict[str, Any]]:
    """Compiles skeletons for all weeks, then passes the entire list to the Curriculum Board for macro-polishing."""
    raw_syllabus = []
    for module in weekly_modules:
        week_num = int(module.get('week_number', 1))
        week_title = str(module.get('title', f"Week {week_num}"))
        focus = str(module.get('focus', 'Focus'))
        
        print(f"        -> [Syllabus Drafter] Drafting skeleton for {week_title}...")
        skeleton = generate_premium_weekly_skeleton(base_title, week_title, focus, client_persona, locale)
        raw_syllabus.append({
            "week_title": week_title,
            "days": skeleton.get('days', []) if skeleton else []
        })
        
    print(f"        -> [Curriculum Board] Auditing the complete {len(weekly_modules)}-week syllabus for macro-flow and repetition...")
    audited_syllabus = audit_full_program_syllabus(raw_syllabus, base_title, client_persona, locale)
    return audited_syllabus if audited_syllabus else raw_syllabus

# ==========================================
# STEP 3B: PREMIUM "DAY-BY-DAY" & OPTION 3
# ==========================================
@retry_llm_call(max_retries=3, delay=1)
def generate_premium_single_day(base_title: str, week_title: str, client_persona: str, template: dict, locale: str = 'uk') -> Optional[AILessonPlan]:
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are an elite Senior AI Developer and Educator. {ANTI_AI_PROMPT} {spelling} Output ONLY valid JSON."
    
    safe_title = template.get('title', 'Study Session')
    is_rest = template.get('is_rest_day', False)

    if is_rest:
        special_rules = "This is a REST/CONSOLIDATION day. Keep fields brief, emphasizing the neuroscience of learning and letting concepts settle."
    else:
        special_rules = """This is a TECHNICAL LEARNING day.
    You MUST provide highly detailed, expert-level content across these specific fields:
    1. 'theory_lesson': Advanced theoretical breakdown (e.g., tokenization mechanics, parameter sizing, latent space).
    2. 'practical_exercise': A highly actionable step. If they are a dev, include a pseudo-code snippet or JSON payload. If an executive, provide a strict, advanced prompt framework.
    3. 'real_world_case_study': Cite a specific, realistic enterprise use-case.
    4. 'mindset_focus': High-level strategic thinking.
    """

    user_prompt = f"""
    Task: Write the highly detailed, elite protocols for a SINGLE day of AI learning.

    Program: {base_title}
    Week: {week_title}
    Client Profile: {client_persona}
    Day Title: {safe_title}

    CRITICAL PREMIUM RULES:
    1. {special_rules}
    2. CRITICAL: NEVER output `null` values.
    3. Use Markdown formatting heavily.

--- EXPECTED JSON FORMAT ---
    {{
        "theory_lesson": "**The Mechanics:** [Provide FULL, comprehensive theory lesson here. Do not truncate.]",
        "practical_exercise": "**Implementation:** [Provide detailed step-by-step instructions] \\n\\n```python\\n[Provide FULL, comprehensive code here. Do not truncate.]\\n```",
        "real_world_case_study": "**Case Study:** [Provide FULL, comprehensive real world case study here. Do not truncate.]",
        "mindset_focus": "**Strategic Shift:** [Provide FULL, comprehensive mindset focus here. Do not truncate.]",
    }}
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.7, 'num_predict': 3000})
    data = extract_json_from_text(response['message']['content'])
    
    if data and isinstance(data, dict): 
        return AILessonPlan.from_dict(data, fallback_title=safe_title, is_rest=is_rest)
    return None

@retry_llm_call(max_retries=2, delay=1)
def apply_premium_self_correction(draft_plan: AILessonPlan, client_persona: str, day_title: str, is_rest_day: bool, locale: str = 'uk') -> Optional[AILessonPlan]:
    if is_rest_day:
        return draft_plan

    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are a Staff Engineer reviewing a junior technical writer's work. {ANTI_AI_PROMPT} {spelling} Output ONLY valid JSON."
    
    user_prompt = f"""
    Task: Critique and immediately rewrite this drafted AI lesson to make it ELITE.
    
    Client Profile: {client_persona}
    Day Title: {day_title}
    
    --- JUNIOR WRITER'S DRAFT ---
    {json.dumps(asdict(draft_plan), indent=2)}
    
    --- CRITIQUE & REWRITE RULES ---
    1. 'theory_lesson': Is it too basic? Inject technical depth (latency limits, context window optimization, data sanitization).
    2. 'practical_exercise': Is it just "go ask ChatGPT"? If so, REWRITE it to include a strict prompt template, API curl request, or specific Python/JSON pseudo-code snippet. Ensure the code snippet is FULL and comprehensive, do not truncate it. 
    3. 'real_world_case_study': Make sure it sounds like a real enterprise SaaS case study, not a generic hypothetical.
    
    Output the completely rewritten, perfected JSON using the exact same keys.
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.4, 'num_predict': 3000})
    data = extract_json_from_text(response['message']['content'])
    
    if data and isinstance(data, dict): 
        return AILessonPlan.from_dict(data, fallback_title=day_title, is_rest=is_rest_day)
    return None 

@retry_llm_call(max_retries=4, delay=2)
def audit_completed_week(completed_days_dicts: List[dict], base_title: str, week_title: str, client_persona: str, locale: str = 'uk') -> Optional[List[dict]]:
    """Option 3: Holistic Weekly Polish. Reviews all 7 days to ensure cohesive narrative flow."""
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are a Principal AI Architect & QA Lead. {ANTI_AI_PROMPT} {spelling} Output ONLY valid JSON."
    
    user_prompt = f"""
    Task: Review a full 7-day sprint of highly technical AI curriculum.
    Program: {base_title} | Week: {week_title}
    Profile: {client_persona}
    
    --- WEEKLY CONTENT TO REVIEW ---
    {json.dumps(completed_days_dicts, indent=2)}

    --- QA RULES ---
    1. Narrative Flow: Ensure concepts build on each other. Day 2 should naturally progress from the foundational theory written in Day 1.
    2. Holistic Review: Did the writers use the exact same 'real_world_case_study' twice this week? If so, REWRITE the duplicate to be unique.
    3. CRITICAL OUTPUT FORMAT: Return EXACTLY 7 updated days wrapped in a JSON object under the key "days". Do NOT omit any keys.
    4. PRESERVE MARKDOWN: You MUST preserve all **bold** text and ```code blocks``` from the original draft. Do not summarize them.
    5. STRICT JSON SEPARATION: Do NOT combine fields. You must close the "practical_exercise" string completely before starting the "real_world_case_study" JSON key.
    6. CRITICAL: For 'real_world_case_study', you MUST write a 1-sentence example of how a major tech company uses this exact concept in production. Do NOT output 'N/A'.

    --- EXPECTED JSON FORMAT ---
    {{
        "days": [
            {{
                "day_number": 1,
                "title": "Day 1",
                "is_rest_day": false,
                "theory_lesson": "**The Mechanics:** [Provide FULL, comprehensive theory lesson here. Do not truncate.]",
                "practical_exercise": "**Implementation:** [Provide detailed step-by-step instructions] \\n\\n```python\\n[Provide FULL, comprehensive code here. Do not truncate.]\\n```",
                "real_world_case_study": "**Case Study:** [Provide FULL, comprehensive real world case study here. Do not truncate.]",
                "mindset_focus": "**Strategic Shift:** [Provide FULL, comprehensive mindset focus here. Do not truncate.]",
            }},
            {{
                "day_number": 2,
                "title": "Day 2",
                "is_rest_day": false,
                "theory_lesson": "**The Mechanics:** [Provide FULL, comprehensive theory lesson here. Do not truncate.]",
                "practical_exercise": "**Implementation:** [Provide detailed step-by-step instructions] \\n\\n```python\\n[Provide FULL, comprehensive code here. Do not truncate.]\\n```",
                "real_world_case_study": "**Case Study:** [Provide FULL, comprehensive real world case study here. Do not truncate.]",
                "mindset_focus": "**Strategic Shift:** [Provide FULL, comprehensive mindset focus here. Do not truncate.]",
            }}
        ]
    }}
    CRITICAL: YOU MUST RETURN ALL 7 DAYS. DO NOT TRUNCATE THE ARRAY. DO NOT ADD COMMENTS.
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.3, 'num_predict': 6000})
    data = extract_json_from_text(response['message']['content'])
    
    if data and isinstance(data, dict) and 'days' in data and isinstance(data['days'], list) and len(data['days']) == 7:
        return data['days']
    return None

def orchestrate_premium_week(base_title: str, week_title: str, client_persona: str, week_skeleton_days: list, locale: str = 'uk') -> Dict[str, Any]:
    """Handles the drafting, self-correction, and final holistic weekly audit for Premium tiers."""
    completed_days = []
    
    for template in week_skeleton_days:
        if not isinstance(template, dict):
            template = {"title": str(template)[:100], "is_rest_day": False}

        day_title = template.get('title', 'Study Session')
        is_rest_day = template.get('is_rest_day', False)
        
        print(f"        -> [Premium Drafter] Drafting baseline for: {day_title}...")
        draft_plan = generate_premium_single_day(base_title, week_title, client_persona, template, locale)
        
        if draft_plan and isinstance(draft_plan, AILessonPlan):
            if not is_rest_day:
                print(f"        -> [Premium Refiner] Critiquing and enhancing tech depth for {day_title}...")
            
            final_plan = apply_premium_self_correction(draft_plan, client_persona, day_title, is_rest_day, locale)
            
            if isinstance(final_plan, AILessonPlan):
                template.update(asdict(final_plan))
            else:
                template.update(asdict(draft_plan))
        else:
            log_warning("AI", f"Draft generation completely failed for '{day_title}'. Applying Failsafe Dataclass.")
            template.update(asdict(AILessonPlan(
                title=day_title, is_rest_day=True, theory_lesson="Data unavailable. Read docs.", 
                practical_exercise="Rest.", real_world_case_study="N/A", mindset_focus="Recover."
            )))
        
        completed_days.append(template)
        
    print(f"        -> [QA Agent] Running Weekly Consolidation Pass on '{week_title}' to ensure narrative flow...")
    audited_week = audit_completed_week(completed_days, base_title, week_title, client_persona, locale)
    
    if audited_week:
        return {"days": audited_week}
    else:
        log_warning("AI", f"QA Pass failed for '{week_title}' on '{base_title}'. Falling back to un-audited week.")
        return {"days": completed_days}

# ==========================================
# STANDARD & BASIC WORKOUT GENERATION
# ==========================================
@retry_llm_call(max_retries=3, delay=1)
def generate_standard_free_lessons(base_title: str, week_title: str, week_focus: str, client_persona: str, tier: str, locale: str = 'uk') -> Optional[Dict[str, Any]]:
    spelling = get_spelling_instruction(locale)
    system_prompt = f"You are an AI Tech Educator. {ANTI_AI_PROMPT} {spelling} Output ONLY valid JSON."
    
    if tier == "Standard":
        tier_rule = "STANDARD TIER: Provide a solid 3-4 day split of learning and 3 days of consolidation/rest. Include good practical exercises."
    else: 
        tier_rule = "BASIC TIER: Incredibly simple. 2 working days maximum, 5 days of rest/consolidation. Focus on basic definitions."

    user_prompt = f"""
    Task: Design the daily lessons for "{week_title}" of "{base_title}".
    CRITICAL TIER RULE: {tier_rule}
    
    Rules:
    1. Output a JSON object with a 'days' array containing EXACTLY 7 unique items (Day 1 to 7).
    2. 'days' must include 'title', 'is_rest_day', 'theory_lesson', 'practical_exercise', 'real_world_case_study', and 'mindset_focus'.
    3. Every day must be distinct. DO NOT REPEAT CONTENT.
    4. Do NOT use 'null' for Rest days. Provide a short text string explaining why they are resting.
    5. PRESERVE MARKDOWN: You MUST preserve all **bold** text and ```code blocks``` from the original draft.
    6. STRICT JSON SEPARATION: Do NOT combine fields. You must close the "practical_exercise" string completely before starting the "real_world_case_study" JSON key.
    7. CRITICAL: For 'real_world_case_study', you MUST write a 1-sentence example of how a major tech company uses this exact concept in production. Do NOT output 'N/A'.

    --- EXPECTED JSON FORMAT ---
    {{
        "days": [
            {{
                "day_number": 1,
                "title": "Day 1",
                "is_rest_day": false,
                "theory_lesson": "**The Mechanics:** [Provide FULL, comprehensive theory lesson here. Do not truncate.]",
                "practical_exercise": "**Implementation:** [Provide detailed step-by-step instructions] \\n\\n```python\\n[Provide FULL, comprehensive code here. Do not truncate.]\\n```",
                "real_world_case_study": "**Case Study:** [Provide FULL, comprehensive real world case study here. Do not truncate.]",
                "mindset_focus": "**Strategic Shift:** [Provide FULL, comprehensive mindset focus here. Do not truncate.]",
            }},
            {{
                "day_number": 2,
                "title": "Day 2",
                "is_rest_day": false,
                "theory_lesson": "**The Mechanics:** [Provide FULL, comprehensive theory lesson here. Do not truncate.]",
                "practical_exercise": "**Implementation:** [Provide detailed step-by-step instructions] \\n\\n```python\\n[Provide FULL, comprehensive code here. Do not truncate.]\\n```",
                "real_world_case_study": "**Case Study:** [Provide FULL, comprehensive real world case study here. Do not truncate.]",
                "mindset_focus": "**Strategic Shift:** [Provide FULL, comprehensive mindset focus here. Do not truncate.]",
            }}
        ]
    }}
    CRITICAL: YOU MUST RETURN ALL 7 DAYS. DO NOT TRUNCATE THE ARRAY. DO NOT ADD COMMENTS.

    --- ACTUAL TASK ---
    Base Title: "{base_title}"
    Week Title: "{week_title}"
    Week Focus: "{week_focus}"
    Profile: "{client_persona}"
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], format='json', options={'temperature': 0.6, 'num_predict': 2500})
    data = extract_json_from_text(response['message']['content'])
    if data and isinstance(data, dict) and 'days' in data and isinstance(data['days'], list): 
        return data
    return None

# ==========================================
# MASTER PIPELINE
# ==========================================
def generate_full_tiered_package(client_persona, total_weeks=4, locale_arg='both'):
    print(f"\n=====================================================")
    print(f"STARTING TIERED AI GENERATION FOR: '{client_persona}'")
    print(f"=====================================================\n")
    
    # --- 1. SHARED STRUCTURAL ARCHITECTURE (Run Once) ---
    print(">>> PHASE 1: BUILDING SHARED ARCHITECTURE <<<")
    base_concept = generate_base_concept(client_persona, total_weeks, 'uk')
    if not base_concept:
        print("Failed to build base concept.")
        return False
        
    base_title = str(base_concept.get('base_title', 'AI Learning Path'))
    print(f"SUCCESS: Locked in Base Concept -> '{base_title}'")

    modules = base_concept.get('weekly_modules', [])
    if not isinstance(modules, list):
        modules = []
        
    print(f"      [Premium] Generating and Auditing Shared Curriculum Syllabus...")
    shared_premium_syllabus = compile_and_audit_syllabus(base_title, modules, client_persona, 'uk')

    tiers = [
        # {"name": "Basic", "price": 0.99, "is_paid": True, "level": "beginner"},
        # {"name": "Standard", "price": 9.99, "is_paid": True, "level": "intermediate"},
        {"name": "Premium", "price": 29.99, "is_paid": True, "level": "advanced"}
    ]

    locales_to_run = ['uk', 'us'] if locale_arg == 'both' else [locale_arg]

    # --- 2. LOCALIZED CONTENT GENERATION (Run Per Locale) ---
    for current_locale in locales_to_run:
        print(f"\n=====================================================")
        print(f"🌍 GENERATING CONTENT FOR REGION: {current_locale.upper()}")
        print(f"=====================================================\n")

        for tier_info in tiers:
            tier_name = tier_info['name']
            print(f"\n---> BUILDING {tier_name.upper()} TIER ({current_locale.upper()}) <---")
            
            marketing = generate_tier_marketing(base_title, client_persona, tier_name, current_locale)
            if not marketing: continue
            
            # --- SAFE SLUG MATH ---
            tier_slug = slugify(tier_name)
            prefix = "ai-"
            allowed_title_len = 200 - len(prefix) - len(tier_slug) - len(current_locale) - 2 # -2 for the dashes
            base_slug = slugify(base_title)[:allowed_title_len].rstrip('-')
            safe_slug = f"{prefix}{base_slug}-{tier_slug}-{current_locale}"
            # ----------------------

            full_title = f"{base_title} ({tier_name} Access - {current_locale.upper()})"

            science_block = str(marketing.get('industry_impact', ''))
            marketing_text = str(marketing.get('long_description', ''))
            persona_block = f"**Course Specifications:**\nDesigned for: *{client_persona}*"
            
            description_parts = []
            if science_block:
                description_parts.append(f"<div class='bg-emerald-50 text-emerald-900 p-4 rounded-lg border border-emerald-200 font-medium'>\n\n{science_block}\n\n</div>")
            if marketing_text:
                description_parts.append(f"\n\n---\n\n{marketing_text}")
            description_parts.append("\n\n---\n\n")
            description_parts.append(persona_block)
            
            final_long_description = "".join(description_parts)

            # ---------------------------------------------------------
            # EARLY VALIDATION & DB SAVE
            # ---------------------------------------------------------
            try:
                path, _ = AILearningPath.objects.update_or_create(
                    slug=safe_slug,
                    defaults={
                        'title': full_title[:250],
                        'target_audience': str(base_concept.get('target_audience', 'General'))[:255],
                        'level': tier_info['level'],
                        'description': str(marketing.get('description', ''))[:500],
                        'long_description': final_long_description,
                        'seo_title': str(marketing.get('seo_title', full_title))[:255],
                        'meta_description': str(marketing.get('meta_description', ''))[:255],
                        'is_published': True,
                        'static_image_path': '/portfolio/images/cards/julian-stone-AI.jpg',
                        'is_paid': tier_info['is_paid']
                    }
                )

                # if tier_name in ['Premium', 'Standard']:
                #     equip_name = str(marketing.get('recommended_equipment_name', ''))
                #     amazon_link = f"https://www.amazon.co.uk/s?k={urllib.parse.quote_plus(equip_name)}&tag=julianstone-21" if equip_name else ""
                    
                #     ShopProduct.objects.update_or_create(
                #         slug=safe_slug,
                #         defaults={
                #             'title': f"{full_title[:230]} - Digital Course",
                #             'short_description': str(marketing.get('description', ''))[:200],
                #             'description': str(marketing.get('shop_description', '')),
                #             'price': tier_info['price'],
                #             'is_published': True,
                #             'cover_image': 'https://www.julianstone.co.uk/static/portfolio/images/cards/julian-stone-AI.jpg',
                #             'related_affiliate_product_name': equip_name[:255],
                #             'related_affiliate_link': amazon_link,
                #             'affiliate_pitch': str(marketing.get('equipment_pitch', ''))[:255],
                #         }
                #     )
                #     print(f"  [+] Shop item created. Price: £{tier_info['price']}")

                #     merchant, _ = Merchant.objects.get_or_create(
                #         merchant_id="julian-stone-ai-institute",
                #         defaults={
                #             'name': "Julian Stone AI Institute",
                #             'description': 'Cutting-edge artificial intelligence training.'
                #         }
                #     )
                #     category, _ = AffiliateCategory.objects.get_or_create(
                #         name="AI & Tech Education",
                #         defaults={'slug': 'ai-tech-education'}
                #     )
                #     affiliate_product, _ = AffiliateProduct.objects.update_or_create(
                #         slug=safe_slug,
                #         defaults={
                #             'base_product_name': full_title[:200],
                #             'description': final_long_description,
                #             'merchant': merchant,
                #             'category': category,
                #         }
                #     )

                #     internal_buy_url = f"/shop/{safe_slug}/" 
                #     variant = ProductVariant.objects.filter(product=affiliate_product).first()
                #     if variant:
                #         variant.full_variant_name = str(marketing.get('variant_name', full_title))[:200]
                #         variant.merchant_product_id = safe_slug
                #         variant.price = tier_info['price']
                #         variant.buy_url = internal_buy_url
                #         variant.is_available = True
                #         variant.save()
                #     else:
                #         ProductVariant.objects.create(
                #             product=affiliate_product,
                #             merchant_product_id=safe_slug,
                #             full_variant_name=str(marketing.get('variant_name', full_title))[:200],
                #             price=tier_info['price'],
                #             image_url='https://www.julianstone.co.uk/static/portfolio/images/cards/julian-stone-AI.jpg',
                #             buy_url=internal_buy_url,
                #             is_available=True
                #         )
                # print(f"  [+] DB Validation Passed. Shop & Affiliates Bridged.")
            except Exception as e:
                print(f"  [X] CRITICAL DB ERROR during early validation for {tier_name}: {e}")
                raise e

            # ---------------------------------------------------------
            # 🧠 THE HEAVY LLM LIFTING 🧠
            # ---------------------------------------------------------
            for module in modules:
                if not isinstance(module, dict):
                    module = {"week_number": 1, "title": str(module)[:100], "focus": "General focus"}
                    
                week_num = int(module.get('week_number', 1))
                week_title = str(module.get('title', f"Week {week_num}"))
                week_focus = str(module.get('focus', 'General focus'))
                
                print(f"      Generating {tier_name} Lessons for: {week_title}...")
                
                week, _ = AIPathWeek.objects.update_or_create(
                    path=path, week_number=week_num,
                    defaults={'title': week_title, 'focus': week_focus}
                )
                
                if tier_name == 'Premium':
                    week_skeleton_days = []
                    if shared_premium_syllabus:
                        for week_data in shared_premium_syllabus:
                            if week_data.get('week_title') == week_title:
                                week_skeleton_days = week_data.get('days', [])
                                break
                    week_data = orchestrate_premium_week(base_title, week_title, client_persona, week_skeleton_days, current_locale)
                else:
                    week_data = generate_standard_free_lessons(base_title, week_title, week_focus, client_persona, tier_name, current_locale)
                
                if not week_data or 'days' not in week_data:
                    continue

                days_list = week_data.get('days', [])
                if not isinstance(days_list, list):
                    days_list = []
                
                for day_of_week in range(1, 8):
                    if day_of_week - 1 < len(days_list):
                        day_data = days_list[day_of_week - 1]
                    else:
                        day_data = {"title": "Study & Review", "is_rest_day": True, "theory_lesson": "Review previous concepts.", "practical_exercise": "None", "real_world_case_study": "None", "mindset_focus": "Consolidate."}
                    
                    if not isinstance(day_data, dict):
                        day_data = {
                            "title": str(day_data)[:250],
                            "theory_lesson": str(day_data),
                            "practical_exercise": "None",
                            "real_world_case_study": "None",
                            "mindset_focus": "Consolidate.",
                            "is_rest_day": False
                        }

                    title_val = str(day_data.get('title') or f"Day {day_of_week}")[:250]
                    theory_val = str(day_data.get('theory_lesson') or 'No theory today.')
                    practical_val = str(day_data.get('practical_exercise') or 'No practical today.')
                    real_world_val = str(day_data.get('real_world_case_study') or 'N/A')
                    mind_val = str(day_data.get('mindset_focus') or 'Stay focused.')
                    is_rest_val = bool(day_data.get('is_rest_day', False))
                    
                    AIPathDay.objects.update_or_create(
                        week=week, day_number=day_of_week,
                        defaults={
                            'title': title_val,
                            'theory_lesson': theory_val,
                            'practical_exercise': practical_val,
                            'real_world_case_study': real_world_val,
                            'mindset_focus': mind_val
                        }
                    )

    print(f"\n=====================================================")
    print(f"SUCCESS: All Tiers & Locales Generated for '{base_title}'")
    print(f"=====================================================\n")
    return True

# ==========================================
# BATCH GENERATOR
# ==========================================
def run_auto_generator(limit, weeks, locale='uk'):
    from django.conf import settings
    history_file = os.path.join(settings.BASE_DIR, 'data_import', 'generated_tiered_ai_log.json')
    rejected_file = os.path.join(settings.BASE_DIR, 'data_import', 'rejected_ai_personas_log.json')
    error_log_file = os.path.join(settings.BASE_DIR, 'data_import', 'critical_errors_log.txt')

    try:
        with open(history_file, 'r') as f: used_personas = set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError): used_personas = set()
        
    try:
        with open(rejected_file, 'r') as f: rejected_personas = set(json.load(f))
    except: rejected_personas = set()

    all_combinations = []
    for combo in itertools.product(EXPERIENCE_LEVELS, AI_TOPICS, GOALS, TIME_AVAILABLE):
        if is_valid_ai_combination(*combo): all_combinations.append(combo)
            
    all_persona_strings = []
    for exp, topic, goal, time_avail in all_combinations:
        article = "An" if exp.lower().startswith(tuple('aeiou')) else "A"
        base_string = f"{article} {exp}. Topic: {topic}. Goal: {goal}. Time available: {time_avail}."
        all_persona_strings.append(base_string)
    
    remaining_personas = [p for p in all_persona_strings if p not in used_personas and p not in rejected_personas]
    
    if len(remaining_personas) == 0:
        print("SUCCESS: All combinations generated or evaluated!")
        return

    random.shuffle(remaining_personas)
    
    success_count = 0
    newly_used = []
    newly_rejected = []
    
    print(f"\nINFO: Commencing AI Gatekeeper Pipeline. Target: {limit} programs.\n")
    
    while success_count < limit and remaining_personas:
        persona_string = remaining_personas.pop(0)
        
        print(f"--- EVALUATING COMBINATION ---")
        print(f"Persona: {persona_string}")
        
        eval_result = evaluate_persona_viability(persona_string)
        if not eval_result:
            print(f"  [X] AI GATEKEEPER FAILED (No valid JSON returned). Skipping.")
            continue
            
        is_viable, reason = eval_result
        if not is_viable:
            print(f"  [X] AI GATEKEEPER REJECTED: {reason}")
            newly_rejected.append(persona_string)
            continue 
            
        print(f"  [+] AI GATEKEEPER APPROVED: {reason}")
        print(f"  --> GENERATING FULL TIERED PACKAGE {success_count + 1}/{limit}...")
        
        try:
            success = generate_full_tiered_package(persona_string, weeks, locale)
            if success:
                success_count += 1
                newly_used.append(persona_string)
        except Exception as e:
            error_msg = f"CRITICAL ERROR generating tiered program for '{persona_string}': {e}"
            print(error_msg)
            
            os.makedirs(os.path.dirname(error_log_file), exist_ok=True)
            with open(error_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] AI SCRIPT: {error_msg}\n")
                
            continue
            
    if newly_used:
        used_personas.update(newly_used)
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, 'w') as f: json.dump(list(used_personas), f, indent=4)
            
    if newly_rejected:
        rejected_personas.update(newly_rejected)
        os.makedirs(os.path.dirname(rejected_file), exist_ok=True)
        with open(rejected_file, 'w') as f: json.dump(list(rejected_personas), f, indent=4)

    print(f"\n=========================================")
    print(f"BATCH COMPLETE: {success_count} generated, {len(newly_rejected)} illogical combinations rejected.")
    print(f"=========================================")

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Tiered AI Path Generator")
#     parser.add_argument('--persona', type=str)
#     parser.add_argument('--auto', action='store_true')
#     parser.add_argument('--limit', type=int, default=1)
#     parser.add_argument('--weeks', type=int, default=4)
#     parser.add_argument('--locale', type=str, default='uk', choices=['uk', 'us', 'both'])
    
#     args = parser.parse_args()
    
#     if args.auto: run_auto_generator(args.limit, args.weeks, args.locale)
#     elif args.persona: generate_full_tiered_package(args.persona, args.weeks, args.locale)
#     else: print("Please provide --persona or --auto")
