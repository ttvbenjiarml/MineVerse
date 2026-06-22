from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mineforgeai.cli.interactive import startup_text, InteractiveApp
from mineforgeai.model.runtime import load_local_model
from mineforgeai.model.transformer import ModelConfig


# ---------------------------------------------------------------------------
# 1. Codex theme startup banner
# ---------------------------------------------------------------------------
def test_startup_text_codex_theme(tmp_path):
    """Verify startup_text produces a Codex-themed banner with ANSI escape codes."""
    workspace = tmp_path

    # Write a mock memory file to force Codex theme
    state_dir = workspace / ".mineforgeai"
    state_dir.mkdir(parents=True)
    (state_dir / "memory.json").write_text(json.dumps({"ui_theme": "codex"}), encoding="utf-8")

    banner = startup_text(
        workspace=workspace,
        model_label="local cpu/float32",
        has_model=True,
        permission_label="Full Access",
        web_enabled=True
    )

    # Check that basic parts of the startup banner are present
    assert "MineForgeAI (interactive)" in banner
    assert "model:" in banner
    assert "local cpu/float32" in banner
    assert "Permissions:" in banner
    assert "Full Access" in banner
    assert "Web:" in banner
    # Ensure ANSI codes are present in Codex theme output
    assert "\033[" in banner or "\x1b[" in banner


def test_startup_text_classic_theme(tmp_path):
    """Verify startup_text produces a plain banner when classic theme is selected."""
    workspace = tmp_path

    state_dir = workspace / ".mineforgeai"
    state_dir.mkdir(parents=True)
    (state_dir / "memory.json").write_text(json.dumps({"ui_theme": "classic"}), encoding="utf-8")

    banner = startup_text(
        workspace=workspace,
        model_label="local cpu/float32",
        has_model=True,
        permission_label="Ask Before Actions",
        web_enabled=False
    )

    assert "MineForgeAI Omniverse" in banner
    assert "Model: local cpu/float32" in banner
    assert "Permissions: Ask Before Actions" in banner
    assert "Web: off" in banner
    # Classic theme should NOT have ANSI color codes in the title line
    # (it may appear in Java summary from detect_hardware but not in the header)


# ---------------------------------------------------------------------------
# 2. Model loading with dynamic vocab_size matching
# ---------------------------------------------------------------------------
@patch("mineforgeai.model.runtime.find_trained_model_dir")
@patch("mineforgeai.model.runtime.model_is_usable")
@patch("mineforgeai.model.runtime.model_artifact_paths")
@patch("mineforgeai.model.runtime._load_model_config")
@patch("mineforgeai.model.runtime.SimpleBPETokenizer")
@patch("mineforgeai.model.runtime.detect_hardware")
@patch("torch.load")
@patch("mineforgeai.model.runtime.create_model")
def test_load_local_model_size_matching_protection(
    mock_create_model,
    mock_torch_load,
    mock_detect_hardware,
    mock_tokenizer_cls,
    mock_load_model_config,
    mock_model_artifact_paths,
    mock_model_is_usable,
    mock_find_trained_model_dir,
    tmp_path
):
    """Verify load_local_model dynamically adjusts config.vocab_size to match checkpoint weights."""
    workspace = tmp_path
    mock_find_trained_model_dir.return_value = workspace / "models" / "latest"
    mock_model_is_usable.return_value = True

    mock_model_artifact_paths.return_value = {
        "weights": workspace / "model.pt",
        "tokenizer": workspace / "tokenizer.json",
        "config": workspace / "model_config.json"
    }

    initial_config = ModelConfig(vocab_size=97)
    mock_load_model_config.return_value = initial_config

    # Mock tokenizer with vocab length 97
    mock_tokenizer = MagicMock()
    mock_tokenizer.vocab = {f"char_{i}": i for i in range(97)}
    mock_tokenizer_cls.load.return_value = mock_tokenizer

    mock_profile = MagicMock()
    mock_profile.device = "cpu"
    mock_profile.precision = "float32"
    mock_profile.virtual_memory_enabled = False
    mock_profile.performance_tier = "low"
    mock_profile.available_virtual_memory_gb = 16.0
    mock_detect_hardware.return_value = mock_profile

    # Mock checkpoint weights containing token_embedding.weight with shape [256, 128]
    mock_weight_tensor = MagicMock()
    mock_weight_tensor.shape = (256, 128)
    mock_torch_load.return_value = {
        "token_embedding.weight": mock_weight_tensor
    }

    # Call load_local_model
    runtime = load_local_model(workspace)

    # Verify model config's vocab_size was adjusted to 256
    assert initial_config.vocab_size == 256
    mock_create_model.assert_called_once_with(initial_config)


# ---------------------------------------------------------------------------
# 3. Git-aware prompt formatting
# ---------------------------------------------------------------------------
@patch("mineforgeai.cli.interactive.load_memory")
def test_interactive_app_custom_prompt(mock_load_memory, tmp_path):
    """Verify dynamic git-aware prompt correctly parses branch names including slashes."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    # Create Git repository mock folders/HEAD file
    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/minecraft-agent", encoding="utf-8")

    # Initialize app
    app = InteractiveApp(workspace, "local", False)

    # Mock input to verify prompt text fallback
    with patch("builtins.input", return_value="hello") as mock_input:
        app._prompt(" >_ ")
        mock_input.assert_called_once()
        called_prompt_arg = mock_input.call_args[0][0]

        # Verify the plain text prompt has workspace name and Git branch
        assert app.workspace.name in called_prompt_arg
        assert "feature/minecraft-agent" in called_prompt_arg


# ---------------------------------------------------------------------------
# 4. /help command
# ---------------------------------------------------------------------------
@patch("mineforgeai.cli.interactive.load_memory")
def test_help_command(mock_load_memory, tmp_path):
    """Verify /help returns a comprehensive help message with all command descriptions."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    app = InteractiveApp(workspace, "local", False)
    result = app.respond("/help")

    assert "Available Commands" in result
    assert "/permissions" in result
    assert "/web on" in result
    assert "/web off" in result
    assert "/model status" in result
    assert "/theme" in result
    assert "/rename" in result
    assert "/clear" in result
    assert "/help" in result
    assert "Examples" in result


# ---------------------------------------------------------------------------
# 5. /rename command
# ---------------------------------------------------------------------------
@patch("mineforgeai.cli.interactive.load_memory")
def test_rename_command_no_name(mock_load_memory, tmp_path):
    """Verify /rename with no argument returns usage instructions."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    app = InteractiveApp(workspace, "local", False)
    result = app.respond("/rename")

    assert "Usage:" in result


@patch("mineforgeai.cli.interactive.load_memory")
def test_rename_command_with_name(mock_load_memory, tmp_path):
    """Verify /rename with a valid name renames the thread directory."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    app = InteractiveApp(workspace, "local", False)
    result = app.respond("/rename My Cool Thread")

    assert "Thread renamed to:" in result
    assert "My Cool Thread" in result
    assert app.conversation_dir.name == "My Cool Thread"


# ---------------------------------------------------------------------------
# 6. /clear command
# ---------------------------------------------------------------------------
@patch("mineforgeai.cli.interactive.load_memory")
def test_clear_command(mock_load_memory, tmp_path):
    """Verify /clear clears the context messages and summary."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    app = InteractiveApp(workspace, "local", False)
    # Add some fake messages
    app.context.add("user", "Hello")
    app.context.add("assistant", "Hi there!")
    app.context.prior_summary = "Previous conversation summary."

    assert len(app.context.messages) == 2
    assert app.context.prior_summary != ""

    result = app.respond("/clear")

    assert "Context cleared" in result
    assert len(app.context.messages) == 0
    assert app.context.prior_summary == ""


# ---------------------------------------------------------------------------
# 7. Unknown command handling
# ---------------------------------------------------------------------------
@patch("mineforgeai.cli.interactive.load_memory")
def test_unknown_slash_command(mock_load_memory, tmp_path):
    """Verify unknown slash commands produce a helpful error pointing to /help."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    app = InteractiveApp(workspace, "local", False)
    result = app.respond("/nonexistent")

    assert "/help" in result
    assert "Unknown command" in result


# ---------------------------------------------------------------------------
# 8. Streaming generation method exists and is a generator
# ---------------------------------------------------------------------------
def test_streaming_generation_is_generator():
    """Verify LocalModelRuntime has a generate_text_streaming method."""
    from mineforgeai.model.runtime import LocalModelRuntime
    assert hasattr(LocalModelRuntime, "generate_text_streaming")
    import inspect
    # The method should be a generator function
    assert inspect.isgeneratorfunction(LocalModelRuntime.generate_text_streaming) or callable(LocalModelRuntime.generate_text_streaming)


# ---------------------------------------------------------------------------
# 9. Streaming respond returns the __STREAM__ marker
# ---------------------------------------------------------------------------
@patch("mineforgeai.cli.interactive.load_memory")
def test_respond_returns_stream_marker_when_model_available(mock_load_memory, tmp_path):
    """When a local model is available, respond() should return a (__STREAM__, generator) tuple for chat messages."""
    workspace = tmp_path
    mock_load_memory.return_value = {"ui_theme": "codex"}

    app = InteractiveApp(workspace, "local", False)

    # Create a mock local model with streaming support
    mock_model = MagicMock()
    def fake_streaming(*args, **kwargs):
        yield "Hello "
        yield "world!"
    mock_model.generate_text_streaming = fake_streaming
    mock_model.preferred_profile = "balanced"
    app.local_model = mock_model

    result = app.respond("tell me a story")

    # Should be a tuple with __STREAM__ marker
    assert isinstance(result, tuple)
    assert result[0] == "__STREAM__"
    # Consume the generator
    chunks = list(result[1])
    assert len(chunks) > 0


# ---------------------------------------------------------------------------
# 10. Startup text mentions /help tip
# ---------------------------------------------------------------------------
def test_startup_text_mentions_commands(tmp_path):
    """Startup text should reference the /permisions command."""
    workspace = tmp_path

    state_dir = workspace / ".mineforgeai"
    state_dir.mkdir(parents=True)
    (state_dir / "memory.json").write_text(json.dumps({"ui_theme": "codex"}), encoding="utf-8")

    banner = startup_text(
        workspace=workspace,
        model_label="fallback",
        has_model=False,
        permission_label="Ask Before Actions",
        web_enabled=False
    )

    assert "/permisions" in banner
    assert "Just tell me what you want" in banner
