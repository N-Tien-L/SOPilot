#!/usr/bin/env python3
"""
Test script for Layer 2 Intent Classifier
Run: python test_layer2_intent.py
"""

import asyncio
import os
import sys
from groq import AsyncGroq

# Set UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_test_key_placeholder")

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an AI policy assistant.
Your task: Classify the user query as [SIMPLE] or [COMPLEX].

[SIMPLE]: Questions that DO NOT require searching internal documents.
If an ordinary person without special knowledge could answer confidently, it is SIMPLE.
Examples:
- "Hello, how are you?" -> SIMPLE
- "What is 2 + 2?" -> SIMPLE
- "Thank you, goodbye!" -> SIMPLE
- "Who is the CEO of this company?" -> SIMPLE (general knowledge)
- "I hate you, you are bad" -> SIMPLE (emotional feedback)
- "What's the weather today?" -> SIMPLE
- "What are you? Who made you?" -> SIMPLE (bot meta-talk)
- "Thanks, bye!" -> SIMPLE (closing talk)

[COMPLEX]: Questions that REQUIRE searching internal documents/policies.
If you would need to look up a document/policy to answer correctly, it is COMPLEX.
Examples:
- "What is our company's remote work policy?" -> COMPLEX
- "How many vacation days am I entitled to?" -> COMPLEX
- "What are the expense reimbursement procedures?" -> COMPLEX
- "What are the security requirements for passwords?" -> COMPLEX
- "How do I request time off?" -> COMPLEX

Rule: If an ordinary person without special knowledge could answer confidently -> SIMPLE.
If you would need to look up a document/policy to answer correctly -> COMPLEX.

User Query: {query}

Recent conversation:
{recent_history}

Return ONLY one word: [SIMPLE] or [COMPLEX]"""

# Test cases - English only for now to avoid encoding issues
SIMPLE_TESTS = [
    ("Hello, how are you?", "SIMPLE"),
    ("Hi there!", "SIMPLE"),
    ("Good morning!", "SIMPLE"),
    ("What are you?", "SIMPLE"),
    ("Who made you?", "SIMPLE"),
    ("What is your name?", "SIMPLE"),
    ("I hate you", "SIMPLE"),
    ("You are bad", "SIMPLE"),
    ("You are useless", "SIMPLE"),
    ("Who is the CEO?", "SIMPLE"),
    ("What is 2 + 2?", "SIMPLE"),
    ("What's the weather?", "SIMPLE"),
    ("Thank you, goodbye!", "SIMPLE"),
    ("Thanks, bye!", "SIMPLE"),
    ("Can you help me?", "SIMPLE"),
]

COMPLEX_TESTS = [
    ("What is our remote work policy?", "COMPLEX"),
    ("How many vacation days am I entitled to?", "COMPLEX"),
    ("What are the expense reimbursement procedures?", "COMPLEX"),
    ("What are the security requirements for passwords?", "COMPLEX"),
    ("How do I request time off?", "COMPLEX"),
    ("How to submit an expense report?", "COMPLEX"),
    ("What is the dress code?", "COMPLEX"),
    ("Can I work from home?", "COMPLEX"),
    ("What are the benefits available?", "COMPLEX"),
    ("How to reset my password?", "COMPLEX"),
    ("What is the remote work policy?", "COMPLEX"),
    ("How many sick days per year?", "COMPLEX"),
    ("What is the travel policy?", "COMPLEX"),
    ("How to request equipment?", "COMPLEX"),
    ("What is the onboarding process?", "COMPLEX"),
]

async def test_intent_classifier():
    client = AsyncGroq(api_key=GROQ_API_KEY)
    
    print("=" * 70)
    print("TESTING LAYER 2 INTENT CLASSIFIER")
    print("=" * 70)
    
    results = {
        "simple_correct": 0,
        "simple_wrong": 0,
        "complex_correct": 0,
        "complex_wrong": 0,
        "errors": 0
    }
    
    # Test SIMPLE cases
    print("\n--- Testing SIMPLE queries (should NOT need RAG) ---")
    for query, expected in SIMPLE_TESTS:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query, recent_history="None")
        
        try:
            response = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0,
            )
            
            raw = response.choices[0].message.content.strip().upper()
            intent = "SIMPLE" if "SIMPLE" in raw else "COMPLEX"
            
            if intent == expected:
                results["simple_correct"] += 1
                print(f"  [OK] {expected}: {query[:35]}...")
            else:
                results["simple_wrong"] += 1
                print(f"  [WRONG] Expected {expected} got {raw[:20]} | {query[:35]}...")
                
        except Exception as e:
            results["errors"] += 1
            print(f"  [ERROR] {query[:35]}...: {str(e)[:50]}")
    
    # Test COMPLEX cases
    print("\n--- Testing COMPLEX queries (SHOULD need RAG) ---")
    for query, expected in COMPLEX_TESTS:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query, recent_history="None")
        
        try:
            response = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0,
            )
            
            raw = response.choices[0].message.content.strip().upper()
            intent = "SIMPLE" if "SIMPLE" in raw else "COMPLEX"
            
            if intent == expected:
                results["complex_correct"] += 1
                print(f"  [OK] {expected}: {query[:35]}...")
            else:
                results["complex_wrong"] += 1
                print(f"  [WRONG] Expected {expected} got {raw[:20]} | {query[:35]}...")
                
        except Exception as e:
            results["errors"] += 1
            print(f"  [ERROR] {query[:35]}...: {str(e)[:50]}")
    
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    total_simple = len(SIMPLE_TESTS)
    total_complex = len(COMPLEX_TESTS)
    
    print(f"\nSIMPLE queries: {results['simple_correct']}/{total_simple} correct ({results['simple_correct']*100//total_simple}%)")
    print(f"  Wrong (classified as COMPLEX): {results['simple_wrong']}")
    
    print(f"\nCOMPLEX queries: {results['complex_correct']}/{total_complex} correct ({results['complex_correct']*100//total_complex}%)")
    print(f"  Wrong (classified as SIMPLE): {results['complex_wrong']}")
    
    print(f"\nTotal errors: {results['errors']}")
    
    total = total_simple + total_complex
    correct = results['simple_correct'] + results['complex_correct']
    accuracy = correct * 100 // total
    print(f"\nOverall accuracy: {accuracy}% ({correct}/{total})")

asyncio.run(test_intent_classifier())