export const DEFAULT_CONFIG = {
  project: {
    name: "MineForgeAI Omniverse",
    workspace_mode: "current_directory_only"
  },
  install: {
    npm_wrapper: true,
    python_backend: true,
    auto_create_venv: true,
    auto_install_requirements: true,
    user_data_dir: "auto",
    cache_dir: "auto"
  },
  device: {
    auto_detect: true,
    prefer_cuda: true,
    prefer_rocm: true,
    prefer_mps: true,
    allow_cpu: true,
    mixed_precision: "auto"
  },
  training: {
    from_scratch: true,
    train_hours: 6,
    resume: true,
    checkpoint_dir: "checkpoints",
    final_model_dir: "models/latest",
    save_every_minutes: 10,
    eval_every_minutes: 10
  },
  chat: {
    auto_start_model: true,
    default_mode: "chatbot",
    auto_compact: true,
    compact_at_context_percent: 75,
    keep_recent_messages: 20
  },
  permissions: {
    default_mode: "ask_before_actions",
    allowed_modes: ["see_edits", "ask_before_actions", "full_access", "custom"],
    show_diffs_before_edit: true,
    block_dangerous_commands: true,
    block_workspace_escape: true
  },
  web: {
    enabled: false,
    controlled_by_command_only: true,
    command_on: "/web on",
    command_off: "/web off",
    prefer_official_docs: true,
    respect_robots_txt: true,
    block_piracy: true
  },
  agent: {
    natural_language_only: true,
    slash_commands_allowed: ["/permisions", "/web on", "/web off"],
    subagents_enabled: true,
    workspace_root: "cwd",
    allow_outside_workspace: false,
    safe_shell_mode: true,
    max_files_read_per_turn: 30,
    max_file_chars: 30000
  }
};
