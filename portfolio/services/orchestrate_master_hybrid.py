import os
import sys
import django
import argparse
import json
import itertools
import random
import time
import urllib.parse
from django.utils.text import slugify
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

# --- SETUP ---
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from ai_concepts.models import TechBootcamp, BootcampWeek, BootcampDay
from shop.models import Product as ShopProduct
from affiliates.models import AffiliateProduct, ProductVariant, Merchant, AffiliateCategory

from llm_utils import (
    patch_windows_console_emojis, extract_json_from_text, 
    get_spelling_instruction, retry_llm_call, hybrid_chat, log_warning
)

patch_windows_console_emojis()
MODEL_NAME = "llama3:latest"

# ==========================================
# 1. UNIVERSAL DATACLASS
# ==========================================
@dataclass
class UniversalDayPlan:
    title: str
    is_rest_day: bool
    theory_lesson: str
    coding_exercise: str
    real_world_application: str
    mindset_focus: str

    @classmethod
    def from_dict(cls, data: dict, fallback_title: str, is_rest: bool) -> 'UniversalDayPlan':
        if not data or not isinstance(data, dict):
            return cls(fallback_title, is_rest, "Theory unavailable.", "No practical today.", "N/A", "Recover.")
        return cls(
            title=data.get('title', fallback_title),
            is_rest_day=data.get('is_rest_day', is_rest),
            theory_lesson=str(data.get('theory_lesson', 'Theory unavailable.')),
            coding_exercise=str(data.get('coding_exercise', data.get('practical_exercise', 'No practical today.'))),
            real_world_application=str(data.get('real_world_application', data.get('real_world_case_study', 'N/A'))),
            mindset_focus=str(data.get('mindset_focus', 'Stay focused.'))
        )

# ==========================================
# 2. THE STRATEGY PATTERN (TOPIC CONFIGURATION)
# ==========================================
def validate_ai(exp, skill, goal, time):
    if exp in ['business executive / founder', 'complete beginner'] and goal == 'integrating AI into existing software': return False
    return True

def validate_ds(exp, skill, goal, time):
    if exp == 'complete beginner' and skill == 'Feature Engineering for Machine Learning': return False 
    return True

def validate_backend(exp, skill, goal, time):
    if skill == 'Python (Core Language)' and 'Django' in goal: return False
    return True

def validate_tech(exp, skill, goal, time):
    if exp == 'complete beginner' and skill == 'API Integration & Data Handling': return False 
    return True

TOPIC_CONFIG = {
    'AI': {
        'db_category': 'AI',
        'prefix': 'ai-',
        'image': '/static/portfolio/images/cards/julian-stone-AI.jpg',
        'merchant_id': 'julian-stone-ai-institute',
        'merchant_name': 'Julian Stone AI Institute',
        'affiliate_cat': 'AI & Tech Education',
        'role_prompt': "Elite AI Researcher and Tech Educator",
        'anti_ai': "Write like an elite, highly technical Silicon Valley engineer, CTO, or AI Researcher. Be concise, authoritative, and practical.",
        'levels': ['complete beginner', 'business executive / founder', 'junior developer upskilling'],
        'skills': ['Generative AI & LLMs', 'AI Agents & Automation', 'Computer Vision', 'RAG Implementations'],
        'goals': ['automating daily business tasks', 'building an AI-powered MVP', 'integrating AI into existing software'],
        'time': ['15 minutes a day', '1 hour a day', 'weekend sprints'],
        'validator': validate_ai,
        'tiers': [
            {"name": "Basic", "price": 0.99, "is_paid": True, "level": "beginner"},
            {"name": "Standard", "price": 9.99, "is_paid": True, "level": "intermediate"},
            {"name": "Premium", "price": 29.99, "is_paid": True, "level": "advanced"}
        ]
    },
    'DS': {
        'db_category': 'DS',
        'prefix': 'data-',
        'image': '/static/portfolio/images/cards/julian-stone-data.jpg',
        'merchant_id': 'julian-stone-data-institute',
        'merchant_name': 'Julian Stone Data Institute',
        'affiliate_cat': 'Data Science & Analytics',
        'role_prompt': "Lead Data Scientist and Big Data Architect",
        'anti_ai': "Write like a Lead Data Scientist. Focus heavily on vectorization, memory-efficient transformations, data wrangling best practices, and statistical accuracy.",
        'levels': ['complete beginner', 'data analyst upskilling', 'software engineer transitioning to data'],
        'skills': ['Pandas Data Manipulation', 'NumPy Scientific Computing', 'Data Visualization', 'ETL Pipelines'],
        'goals': ['transitioning to a data role', 'automating heavy Excel workflows', 'preparing datasets for ML'],
        'time': ['30 minutes a day', '1 to 2 hours a day', 'weekend intensive'],
        'validator': validate_ds,
        'tiers': [
            {"name": "Basic", "price": 0.99, "is_paid": True, "level": "beginner"},
            {"name": "Standard", "price": 9.99, "is_paid": True, "level": "intermediate"},
            {"name": "Premium", "price": 29.99, "is_paid": True, "level": "advanced"}
        ]
    },
    'WEB': {
        'db_category': 'WEB',
        'prefix': 'code-',
        'image': '/static/portfolio/images/cards/julian-stone-python.jpg',
        'merchant_id': 'julian-stone-tech-masterclass',
        'merchant_name': 'Julian Stone Engineering',
        'affiliate_cat': 'Software Engineering',
        'role_prompt': "Senior Staff Backend Engineer and strict Code Reviewer",
        'anti_ai': "Write like a Senior Staff Backend Engineer. Focus on software architecture, Big O notation, and industry best practices. Be pragmatic.",
        'levels': ['junior developer', 'intermediate developer', 'advanced developer'],
        'skills': ['Python (Core Language)', 'Django (Web Framework)', 'Asynchronous Python', 'DRF APIs'],
        'goals': ['mastering system architecture', 'optimizing database queries', 'building scalable microservices'],
        'time': ['1 hour a day', '2 hours a day', 'weekend heavy coding'],
        'validator': validate_backend,
        'tiers': [
            {"name": "Basic", "price": 0.99, "is_paid": True, "level": "beginner"},
            {"name": "Standard", "price": 9.99, "is_paid": True, "level": "intermediate"},
            {"name": "Premium", "price": 29.99, "is_paid": True, "level": "advanced"}
        ]
    },
    'TECH': {
        'db_category': 'TECH',
        'prefix': 'tech-',
        'image': '/static/portfolio/images/cards/julian-stone-python.jpg',
        'merchant_id': 'julian-stone-tech-institute',
        'merchant_name': 'Julian Stone Tech Institute',
        'affiliate_cat': 'Coding & Software Development',
        'role_prompt': "Elite Staff Engineer and Tech Educator",
        'anti_ai': "Write like an Elite Staff Engineer. Focus on clean code, architecture, and real-world deployment.",
        'levels': ['complete beginner', 'hobbyist coder', 'junior developer upskilling'],
        'skills': ['Python Scripting', 'Django Full-Stack', 'Frontend UI with Tailwind', 'Git & Version Control'],
        'goals': ['landing a first tech role', 'building a personal startup MVP', 'automating office tasks'],
        'time': ['30 minutes a day', '1 to 2 hours a day', 'weekend warrior'],
        'validator': validate_tech,
        'tiers': [
            {"name": "Basic", "price": 0.99, "is_paid": True, "level": "beginner"},
            {"name": "Standard", "price": 9.99, "is_paid": True, "level": "intermediate"},
            {"name": "Premium", "price": 29.99, "is_paid": True, "level": "advanced"}
        ]
    }
}

# ==========================================
# 3. UNIFIED LLM FUNCTIONS (Config Injected)
# ==========================================
def get_system_prompt(config: dict, locale: str, extra_role: str = "") -> str:
    spelling = get_spelling_instruction(locale)
    role = extra_role if extra_role else config['role_prompt']
    banned = "BANNED WORDS: delve, testament, beacon, bustling, realm, tapestry, moreover, furthermore, inherently, landscape, embark, elevate, unleash."
    return f"You are a {role}. {spelling} INTERNAL STYLE GUIDE: Do NOT use common AI buzzwords. {banned} {config['anti_ai']} Output ONLY valid JSON."

@retry_llm_call(max_retries=2, delay=1, fallback=(True, "Failsafe bypass."))
def evaluate_persona_viability(persona_string: str, config: dict) -> Tuple[bool, str]:
    user_prompt = f"""
    Task: Evaluate if the following persona makes logical sense for a coding/tech bootcamp.
    Persona: "{persona_string}"
    Output JSON: {{"is_viable": true/false, "reason": "Explanation"}}
    """
    response = hybrid_chat(MODEL_NAME, [{'role': 'system', 'content': get_system_prompt(config, 'uk', "Tech Lead")}, {'role': 'user', 'content': user_prompt}], 'json', {'temperature': 0.1})
    data = extract_json_from_text(response['message']['content'])
    return (data['is_viable'], data.get('reason', '')) if data and 'is_viable' in data else None

@retry_llm_call(max_retries=3, delay=1)
def generate_base_concept(client_persona: str, config: dict, total_weeks: int, locale: str) -> Optional[Dict[str, Any]]:
    user_prompt = f"""
    Task: Design the core architecture for a {total_weeks}-week {config['db_category']} Bootcamp.
    Rules: Output JSON with 'base_title', 'target_skill', and 'weekly_modules' (array of EXACTLY {total_weeks} items with 'week_number', 'title', 'focus').
    Profile: "{client_persona}"
    """
    response = hybrid_chat(MODEL_NAME, [{'role': 'system', 'content': get_system_prompt(config, locale)}, {'role': 'user', 'content': user_prompt}], 'json', {'temperature': 0.7})
    data = extract_json_from_text(response['message']['content'])
    return data if data and 'weekly_modules' in data else None

@retry_llm_call(max_retries=3, delay=1)
def generate_weekly_skeleton(base_title: str, week_title: str, client_persona: str, config: dict, locale: str, tier: str) -> Optional[Dict[str, Any]]:
    # Dynamic Rest Day Rules based on Tier!
    if tier == 'Premium':
        split_rule = "5-6 elite rigorous study days, 1-2 rest/consolidation days."
    elif tier == 'Standard':
        split_rule = "4-5 solid learning days, 2-3 rest days."
    else:
        split_rule = "BASIC/FREE TIER: Keep it simple. 2-3 learning days maximum, 4-5 rest days."

    user_prompt = f"""
    Task: Design the 7-day structural skeleton for "{week_title}" of the "{base_title}" {config['db_category']} bootcamp.
    Tier Level: {tier} | Profile: {client_persona}
    Rules:
    1. Output a JSON object with a 'days' array containing EXACTLY 7 items.
    2. SPLIT RULE: {split_rule}
    3. Day 1 MUST ALWAYS be an active learning day (is_rest_day: false).
    Output JSON format: {{"days": [{{"day_number": 1, "title": "...", "is_rest_day": false}}]}}
    """
    response = hybrid_chat(MODEL_NAME, [{'role': 'system', 'content': get_system_prompt(config, locale)}, {'role': 'user', 'content': user_prompt}], 'json', {'temperature': 0.6})
    data = extract_json_from_text(response['message']['content'])
    return data if data and 'days' in data else None

@retry_llm_call(max_retries=3, delay=1)
def generate_single_day(base_title: str, week_title: str, client_persona: str, template: dict, config: dict, locale: str, tier: str) -> Optional[UniversalDayPlan]:
    safe_title = template.get('title', 'Study Session')
    is_rest = template.get('is_rest_day', False)
    
    # Dynamic Content Rules based on Tier!
    if tier == 'Premium':
        tier_rules = "PREMIUM TIER: Provide highly detailed, expert-level content, rigorous code/theory, and enterprise-level strategy."
    elif tier == 'Standard':
        tier_rules = "STANDARD TIER: Provide clear instructions, practical examples, and solid actionable tips."
    else:
        tier_rules = "BASIC/FREE TIER: Keep it accessible and simple. Focus on high-level definitions."

    rest_rules = "REST DAY: Keep it brief. Use markdown headings." if is_rest else "TECHNICAL DAY: Provide detailed code/theory. MUST use exact markdown headings: **Theory:**, **Objective:**, **Case Study:**, **Strategic Shift:**."

    user_prompt = f"""
    Task: Write the protocols for a SINGLE day of training.
    Program: {base_title} | Week: {week_title} | Day: {safe_title} | Profile: {client_persona}
    Rules: 
    1. {tier_rules}
    2. {rest_rules}
    Output JSON: {{"theory_lesson": "...", "coding_exercise": "...", "real_world_application": "...", "mindset_focus": "..."}}
    """
    response = hybrid_chat(MODEL_NAME, [{'role': 'system', 'content': get_system_prompt(config, locale)}, {'role': 'user', 'content': user_prompt}], 'json', {'temperature': 0.7})
    data = extract_json_from_text(response['message']['content'])
    return UniversalDayPlan.from_dict(data, safe_title, is_rest) if data else None

# ==========================================
# 4. UNIFIED MASTER ORCHESTRATOR
# ==========================================
def generate_full_tiered_package(client_persona: str, config_key: str, total_weeks=4, locale_arg='both'):
    config = TOPIC_CONFIG[config_key]
    print(f"\n=====================================================")
    print(f"STARTING {config_key} GENERATION FOR: '{client_persona}'")
    print(f"=====================================================\n")
    
    base_concept = generate_base_concept(client_persona, config, total_weeks, 'uk')
    if not base_concept: return False
    base_title = str(base_concept.get('base_title', 'Tech Bootcamp'))
    modules = base_concept.get('weekly_modules', [])

    # Dynamically pull the tiers from the topic config!
    tiers = config.get('tiers', [{"name": "Premium", "price": 49.99, "is_paid": True, "level": "advanced"}])
    locales = ['uk', 'us'] if locale_arg == 'both' else [locale_arg]

    for current_locale in locales:
        for tier_info in tiers:
            tier_name = tier_info['name']
            tier_slug = slugify(tier_name)
            safe_slug = f"{config['prefix']}{slugify(base_title)[:150]}-{tier_slug}-{current_locale}"
            full_title = f"{base_title} ({tier_name} - {current_locale.upper()})"

            try:
                # UNIFIED DATABASE SAVE
                program, _ = TechBootcamp.objects.update_or_create(
                    slug=safe_slug,
                    defaults={
                        'title': full_title[:250],
                        'target_skill': str(base_concept.get('target_skill', config_key))[:250],
                        'category': config['db_category'], # INJECTING THE UNIFIED CATEGORY HERE
                        'level': tier_info['level'],
                        'description': f"A comprehensive {config_key} bootcamp tailored for {client_persona}.",
                        'is_published': True,
                        'static_image_path': config['image'],
                        'is_paid': tier_info['is_paid']
                    }
                )
                print(f"  [+] Unified DB Record Created: {full_title}")

                # SHOP & AFFILIATE BRIDGE LOGIC
                # ==========================================
                
                # 1. Create the Shop Showcase Item
                ShopProduct.objects.update_or_create(
                    slug=safe_slug,
                    defaults={
                        'title': f"{full_title[:230]} - Digital Access",
                        'short_description': f"Premium {config_key} mastery designed for {client_persona}"[:255],
                        'description': f"A comprehensive {config_key} curriculum tailored specifically for your goals.",
                        'price': tier_info['price'],
                        'is_published': True,
                        'cover_image': config['image'],
                        # Generating a dynamic Amazon search link based on the topic!
                        'related_affiliate_product_name': f"Recommended {config_key} Reference Guide",
                        'related_affiliate_link': f"https://www.amazon.co.uk/s?k={urllib.parse.quote_plus(config_key + ' programming book')}&tag=julianstone-21",
                        'affiliate_pitch': f"Essential foundational reading for this {config_key} bootcamp.",
                    }
                )
                print(f"  [+] Shop showcase item created. Price: £{tier_info['price']}")

                # 2. Bridge to Affiliates: Merchant
                merchant, _ = Merchant.objects.get_or_create(
                    merchant_id=config['merchant_id'],
                    defaults={
                        'name': config['merchant_name'],
                        'description': f"Premium {config_key} training and resources."
                    }
                )

                # 3. Bridge to Affiliates: Category
                category, _ = AffiliateCategory.objects.get_or_create(
                    name=config['affiliate_cat'],
                    defaults={'slug': slugify(config['affiliate_cat'])}
                )

                # 4. Bridge to Affiliates: Base Product
                affiliate_product, _ = AffiliateProduct.objects.update_or_create(
                    slug=safe_slug,
                    defaults={
                        'base_product_name': full_title[:200],
                        'description': f"A comprehensive {config_key} bootcamp.",
                        'merchant': merchant,
                        'category': category,
                    }
                )

                # 5. Bridge to Affiliates: Product Variant (The routing link)
                internal_buy_url = f"/shop/{safe_slug}/" 
                variant = ProductVariant.objects.filter(product=affiliate_product).first()
                if variant:
                    variant.full_variant_name = full_title[:200]
                    variant.merchant_product_id = safe_slug
                    variant.price = tier_info['price']
                    variant.buy_url = internal_buy_url
                    variant.is_available = True
                    variant.save()
                else:
                    ProductVariant.objects.create(
                        product=affiliate_product,
                        merchant_product_id=safe_slug,
                        full_variant_name=full_title[:200],
                        price=tier_info['price'],
                        image_url=config['image'],
                        buy_url=internal_buy_url,
                        is_available=True
                    )
                print(f"  [+] Affiliates Bridged Successfully.")
                # ==========================================                
            except Exception as e:
                print(f"  [X] CRITICAL DB ERROR: {e}")
                raise e

# WEEK & DAY GENERATION
            for i, module in enumerate(modules):
                week_num = i + 1
                week_title = str(module.get('title', f"Week {week_num}"))
                week, _ = BootcampWeek.objects.update_or_create(bootcamp=program, week_number=week_num, defaults={'title': week_title})
                print(f"      Generating Lessons for: {week_title} ({tier_name} Tier)...")
                
                # 1. Fetch the dynamic skeleton for this specific tier
                skeleton = generate_weekly_skeleton(base_title, week_title, client_persona, config, current_locale, tier_name)
                days_list = skeleton.get('days', []) if skeleton else []
                
                # 2. Generate the 7 days based on the skeleton
                for day_num in range(1, 8):
                    if day_num - 1 < len(days_list):
                        template = days_list[day_num - 1]
                    else:
                        template = {"title": f"Session {day_num}", "is_rest_day": (day_num % 2 == 0)}
                        
                    # Pass the tier_name into the day generator so it adjusts its complexity
                    day_plan = generate_single_day(base_title, week_title, client_persona, template, config, current_locale, tier_name)
                    
                    if not day_plan: 
                        day_plan = UniversalDayPlan(f"Session {day_num}", True, "Read docs.", "Rest.", "N/A", "Focus.")

                    BootcampDay.objects.update_or_create(
                        week=week, day_number=day_num,
                        defaults={
                            'title': day_plan.title[:250],
                            'is_rest_day': day_plan.is_rest_day,
                            'theory_lesson': day_plan.theory_lesson,
                            'coding_exercise': day_plan.coding_exercise,
                            'real_world_application': day_plan.real_world_application,
                            'mindset_focus': day_plan.mindset_focus,
                        }
                    )

    return True

# ==========================================
# 5. UNIFIED BATCH ENGINE
# ==========================================
def run_auto_generator(topic_key: str, limit: int, weeks: int, locale: str):
    config = TOPIC_CONFIG[topic_key]
    
    all_combinations = []
    for combo in itertools.product(config['levels'], config['skills'], config['goals'], config['time']):
        if config['validator'](*combo): 
            all_combinations.append(combo)
            
    random.shuffle(all_combinations)
    success_count = 0
    
    print(f"\nINFO: Commencing UNIFIED {topic_key} Pipeline. Target: {limit} programs.\n")
    
    for combo in all_combinations:
        if success_count >= limit: break
        
        persona = f"Experience: {combo[0]}. Target Skill: {combo[1]}. Goal: {combo[2]}. Time: {combo[3]}."
        print(f"--- EVALUATING --- \n{persona}")
        
        eval_result = evaluate_persona_viability(persona, config)
        if eval_result and eval_result[0]:
            if generate_full_tiered_package(persona, topic_key, weeks, locale):
                success_count += 1
        else:
            print(f"  [X] REJECTED: {eval_result[1] if eval_result else 'JSON Error'}")

# ==========================================
# CLI ENTRY POINT
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Tech Masterclass Generator")
    parser.add_argument('--topic', type=str, required=True, choices=['AI', 'DS', 'WEB', 'TECH'], help="Which topic engine to run")
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--weeks', type=int, default=4)
    parser.add_argument('--locale', type=str, default='both', choices=['uk', 'us', 'both'])
    
    args = parser.parse_args()
    run_auto_generator(args.topic, args.limit, args.weeks, args.locale)