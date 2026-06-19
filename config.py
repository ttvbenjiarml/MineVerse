"""
Top-level configuration for MineVerse local runs.

Edit these values to control basic behavior. This file is intentionally
small and easy to understand.

Fields:
- training_hours: how many hours to plan for training by default
- preferred_mode: one of 'fast', 'balanced', 'quality' for local inference
- auto_install: if True, the launcher will try to pip/npm install missing deps
"""

training_hours = 4.0
preferred_mode = "balanced"  # choices: 'fast', 'balanced', 'quality'
auto_install = True
