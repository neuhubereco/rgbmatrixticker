#!/usr/bin/env python3
"""Skript zum Korrigieren aller rgbmatrix-Imports."""

import os
import re

def fix_file(filepath):
    """Korrigiere rgbmatrix-Imports in einer Datei."""
    if not os.path.exists(filepath):
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Ersetze verschiedene Import-Patterns
    patterns = [
        (r'from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics', 
         'try:\n    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics\nexcept ImportError:\n    from .rgbmatrix_fallback import RGBMatrix, RGBMatrixOptions, graphics'),
        (r'from rgbmatrix import RGBMatrix, RGBMatrixOptions', 
         'try:\n    from rgbmatrix import RGBMatrix, RGBMatrixOptions\nexcept ImportError:\n    from .rgbmatrix_fallback import RGBMatrix, RGBMatrixOptions'),
        (r'from rgbmatrix import graphics', 
         'try:\n    from rgbmatrix import graphics\nexcept ImportError:\n    from .rgbmatrix_fallback import graphics'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ {filepath} korrigiert")
        return True
    else:
        print(f"- {filepath} keine Änderungen nötig")
        return False

def main():
    """Hauptfunktion."""
    files_to_fix = [
        'src/youtube_display.py',
        'src/calendar_manager.py', 
        'src/of_the_day_manager.py',
        'matrix_display.py'
    ]
    
    print("Korrigiere rgbmatrix-Imports...")
    fixed_count = 0
    
    for filepath in files_to_fix:
        if fix_file(filepath):
            fixed_count += 1
    
    print(f"\n{fixed_count} Dateien korrigiert")

if __name__ == "__main__":
    main()
