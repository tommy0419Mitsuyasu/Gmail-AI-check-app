
import os

target_file = r"C:\Users\m.toyoda\.windsurf\Gmail-AI-check-app-main\skill_extractor.py"

print(f"Reading {target_file}...")
with open(target_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Searching for '_find_skill_sections' definition...")
for i, line in enumerate(lines):
    if 'def _find_skill_sections' in line:
        print(f"Line {i+1}: {line.strip()}")
