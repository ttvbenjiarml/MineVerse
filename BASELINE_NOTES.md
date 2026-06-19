# Baseline Notes

This repository ships a minimal but real baseline for a local Minecraft-oriented chatbot and coding agent:

- npm global command: `mineforge`
- Python backend bootstrap and fallback tool mode
- strict slash-command restriction to `/permisions`, `/web on`, `/web off`
- permission-aware file and shell safety model
- local model, tokenizer, trainer, routing, validation, and version-registry scaffolds
- tests covering command restrictions, safety rules, routing, validators, and backend behaviors

The repository is designed to be extended with richer model training data, larger version caches, and deeper platform adapters without changing the user-facing command model.
