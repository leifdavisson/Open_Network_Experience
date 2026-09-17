#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:14b"
OUTPUT_DIR = "/data/Open_Network_Experience/uat-results"
URL = "http://10.98.2.125:8000/"

def query_ollama(prompt, system=""):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.1}
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("response", "").strip()
    except Exception as e:
        return f"Error calling Ollama: {e}"

def run_extraction(content, goal):
    prompt = f"Content:\n{content}\n\nExtraction Goal:\n{goal}\n\nPlease provide a clear, concise analysis."
    return query_ollama(prompt, system="You are an expert QA and UAT automation analyst.")

def run_draft(task_desc, context):
    prompt = f"Task:\n{task_desc}\n\nContext:\n{context}\n\nPlease generate the exact requested format."
    return query_ollama(prompt, system="You are an expert technical QA engineer drafting production UAT reports.")

print("UAT Ollama helper loaded successfully.")
