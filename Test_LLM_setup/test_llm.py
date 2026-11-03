
import gc
import os
from pathlib import Path

import torch

from test_local_llm_basic_setup import LocalLLM


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT_DIR / "models"


# ============================================================
# 2. MODEL CATALOGUE
# Keep repository IDs identical to install_llm.py
# ============================================================

MODEL_CATALOG = {

    "Qwen2.5 0.5B Instruct": {
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "ram_gb": 3,
    },

    "Qwen2.5 1.5B Instruct": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct",
        "ram_gb": 7,
    },

    "Qwen2.5 3B Instruct": {
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "ram_gb": 13,
    },

    "Qwen3.5 2B": {
        "repo": "Qwen/Qwen3.5-2B",
        "ram_gb": 11,
    },

    "SmolLM2 360M Instruct": {
        "repo": "HuggingFaceTB/SmolLM2-360M-Instruct",
        "ram_gb": 2,
    },

    "SmolLM2 1.7B Instruct": {
        "repo": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "ram_gb": 8,
    },

    "Llama 3.2 1B Instruct": {
        "repo": "meta-llama/Llama-3.2-1B-Instruct",
        "ram_gb": 5,
    },

    "Llama 3.2 3B Instruct": {
        "repo": "meta-llama/Llama-3.2-3B-Instruct",
        "ram_gb": 13,
    },

    "TinyLlama 1.1B Chat": {
        "repo": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "ram_gb": 5,
    },

    "Phi-3.5 Mini Instruct": {
        "repo": "microsoft/Phi-3.5-mini-instruct",
        "ram_gb": 17,
    },

    "Gemma 2 2B IT": {
        "repo": "google/gemma-2-2b-it",
        "ram_gb": 10,
    },
}


# ============================================================
# 3. MODEL DIRECTORY
# Same logic as install_llm.py
# ============================================================

def model_directory(details):

    folder = details["repo"].split("/")[-1].lower()

    return MODEL_DIR / folder


# ============================================================
# 4. MODEL VALIDATION
# ============================================================

def has_model_weights(path):

    patterns = [
        "*.safetensors",
        "*.bin",
    ]

    return any(
        any(path.rglob(pattern))
        for pattern in patterns
    )


def is_model_installed(path):

    return (
        (path / "config.json").is_file()
        and has_model_weights(path)
    )


def get_available_ram_gb():

    # Preferred method if psutil is installed.
    try:

        import psutil

        return psutil.virtual_memory().available / (1024 ** 3)

    except ImportError:
        pass

    # Linux fallback.
    try:

        import os

        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")

        return (pages * page_size) / (1024 ** 3)

    except (ValueError, OSError, AttributeError):

        return None


# ============================================================
# 5. DISCOVER INSTALLED MODELS
# ============================================================

def get_installed_models():

    installed = []

    for name, details in MODEL_CATALOG.items():

        path = model_directory(details)

        if is_model_installed(path):

            installed.append(
                (name, details, path)
            )

    return installed


# ============================================================
# 6. DISPLAY AVAILABLE MODELS
# ============================================================

def display_models(models):

    print("\n" + "=" * 70)
    print("             KNOWLEDGEHUB AI - MODEL TESTING")
    print("=" * 70)

    available_ram = get_available_ram_gb()

    if available_ram is not None:

        print(f"\nAvailable system RAM: {available_ram:.2f} GB")

    print("\nInstalled models:")

    for index, (name, details, path) in enumerate(models, 1):

        print(f"\n[{index}] {name}")
        print(f"    Repository : {details['repo']}")
        print(f"    RAM estimate: {details['ram_gb']} GB")
        print(f"    Location   : {path}")

    print("\n" + "-" * 70)

    print("Enter model numbers separated by commas, e.g. 1,2,5")
    print("Enter 'all' to test all installed models.")
    print("Enter 'q' to quit.")

    print("-" * 70)


# ============================================================
# 7. MODEL SELECTION
# ============================================================

def select_models(models):

    display_models(models)

    selection = input("\nYour selection: ").strip().lower()

    if selection == "q":
        return []

    if selection == "all":
        return models

    selected = []

    try:

        indexes = [
            int(item.strip()) - 1
            for item in selection.split(",")
        ]

        for index in indexes:

            if index < 0 or index >= len(models):

                raise ValueError("Selection is outside the available range.")

            if models[index] not in selected:

                selected.append(models[index])

    except ValueError as error:

        print(f"\n[ERROR] Invalid selection: {error}")

        return []

    return selected


# ============================================================
# 8. RAM WARNING
# ============================================================

def confirm_ram_requirement(name, details):

    if torch.cuda.is_available():

        print("[INFO] CUDA GPU detected.")

        return True

    available_ram = get_available_ram_gb()

    if available_ram is None:

        print("[WARNING] Could not determine available system RAM.")

        return input("Continue loading this model? (y/n): ").strip().lower() == "y"

    required_ram = details["ram_gb"]

    print(f"Available RAM: {available_ram:.2f} GB")
    print(f"Estimated RAM: {required_ram} GB")

    if available_ram < required_ram:

        print(
            f"\n[WARNING] Available RAM may be insufficient for {name}."
        )

        return (
            input("Attempt loading anyway? (y/n): ").strip().lower()
            == "y"
        )

    return True


# ============================================================
# 9. TEST MODEL
# ============================================================

def test_model(name, details, path, prompt):

    print("\n" + "=" * 70)
    print(f"TESTING: {name}")
    print("=" * 70)

    llm = None

    try:

        if not confirm_ram_requirement(name, details):

            print("[SKIP] Model skipped because of RAM requirements.")

            return "SKIPPED"

        llm = LocalLLM(
            model_path=str(path),
            repo_id=details["repo"],
        )

        print("\n[GENERATING] Waiting for model response...")

        response = llm.generate(
            prompt,
            max_new_tokens=128,
        )

        print("\nAI RESPONSE:")
        print("-" * 60)
        print(response)
        print("-" * 60)

        print(f"\n[SUCCESS] {name} test completed.")

        return "SUCCESS"

    except Exception as error:

        print(f"\n[FAILED] {name}")
        print(f"Reason: {error}")

        return "FAILED"

    finally:

        if llm is not None:

            llm.unload()

            del llm

        gc.collect()

        if torch.cuda.is_available():

            torch.cuda.empty_cache()


# ============================================================
# 10. MAIN
# ============================================================

def main():

    print("\nKnowledgeHub AI - Local Model Testing")

    models = get_installed_models()

    if not models:

        print("\nNo complete installed models found.")

        print("Run install_llm.py to download models first.")

        return

    selected = select_models(models)

    if not selected:

        print("\nNo models selected.")

        return

    prompt = input("\nEnter your test prompt: ").strip()

    if not prompt:

        prompt = (
            "Explain Retrieval Augmented Generation "
            "in simple terms. Give a practical example."
        )

    results = {
        "SUCCESS": [],
        "FAILED": [],
        "SKIPPED": [],
    }

    for name, details, path in selected:

        result = test_model(
            name,
            details,
            path,
            prompt,
        )

        results[result].append(name)

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("                  MODEL TEST SUMMARY")
    print("=" * 70)

    for status, names in results.items():

        print(f"\n{status}: {len(names)}")

        for name in names:

            print(f"  - {name}")

    print("\nAll selected model tests completed.")


if __name__ == "__main__":
    main()
