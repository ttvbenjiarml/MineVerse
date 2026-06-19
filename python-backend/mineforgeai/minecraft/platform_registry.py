from __future__ import annotations


PLATFORMS = {
    "paper": {
        "id": "paper",
        "name": "Paper",
        "type": "plugin_platform",
        "status": "active",
        "supports_versions": {"strategy": "dynamic"},
        "key_files": ["plugin.yml", "paper-plugin.yml", "build.gradle", "build.gradle.kts"],
        "build_tools": ["Gradle", "Maven"],
        "languages": ["Java", "Kotlin"],
        "common_tasks": ["commands", "listeners", "GUIs", "custom items", "recipes", "configs", "permissions"],
        "common_errors": ["missing plugin.yml", "wrong main class", "unsupported Java version", "missing command registration"],
        "generators": ["paper_java", "paper_kotlin"],
    },
    "fabric": {
        "id": "fabric",
        "name": "Fabric",
        "type": "modloader",
        "status": "active",
        "supports_versions": {"strategy": "dynamic"},
        "key_files": ["fabric.mod.json", "build.gradle", "build.gradle.kts"],
        "build_tools": ["Gradle"],
        "languages": ["Java", "Kotlin"],
        "common_tasks": ["items", "blocks", "recipes", "data generation"],
        "common_errors": ["loader mismatch", "missing entrypoint"],
        "generators": ["fabric_java", "fabric_kotlin"],
    },
}


def get_platform(platform_id: str) -> dict:
    return PLATFORMS[platform_id]
