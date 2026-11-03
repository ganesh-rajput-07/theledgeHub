
#!/usr/bin/env python3

import os
import sys
import subprocess
import importlib.util
import time
import venv

from pathlib import Path


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent
VENV_DIR = ROOT_DIR / ".venv"
MODEL_DIR = ROOT_DIR / "models"

MAX_DOWNLOAD_RETRIES = 3
RETRY_DELAY = 5

if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"


# ============================================================
# 2. AUTOMATIC VIRTUAL ENVIRONMENT SETUP
# ============================================================

def ensure_virtual_environment():

    print("\n" + "=" * 75)
    print("                 PYTHON ENVIRONMENT CHECK")
    print("=" * 75)

    # Case 1: An environment is already activated.
    if sys.prefix != sys.base_prefix:

        print("[SKIP] Virtual environment is already activated.")
        print(f"[INFO] Active environment: {sys.prefix}")

        return

    # Case 2: Project environment already exists.
    if VENV_PYTHON.exists() and (VENV_DIR / "pyvenv.cfg").exists():

        print("[EXISTS] Project virtual environment found.")
        print(f"[INFO] Environment: {VENV_DIR}")

    else:

        # Avoid overwriting an invalid existing environment.
        if VENV_DIR.exists():

            print("[ERROR] An incomplete .venv directory exists.")
            print(f"[INFO] Location: {VENV_DIR}")
            print("Inspect or rename it before running the installer again.")

            sys.exit(1)

        print("[SETUP] Creating virtual environment...")

        try:

            venv.EnvBuilder(with_pip=True).create(VENV_DIR)

            print("[SUCCESS] Virtual environment created.")

        except Exception as error:

            print(f"[ERROR] Could not create virtual environment: {error}")

            if os.name == "posix":

                print("\nUbuntu/Debian installation command:")

                print(
                    f"sudo apt update && sudo apt install "
                    f"python{sys.version_info.major}."
                    f"{sys.version_info.minor}-venv"
                )

            sys.exit(1)

    if not VENV_PYTHON.exists():

        print("[ERROR] Python executable is missing from .venv.")
        sys.exit(1)

    print("[ENVIRONMENT] Restarting inside project virtual environment...")

    os.execv(
        str(VENV_PYTHON),
        [
            str(VENV_PYTHON),
            str(Path(__file__).resolve()),
            *sys.argv[1:]
        ]
    )


# ============================================================
# 3. AUTOMATIC DEPENDENCY INSTALLATION
# ============================================================

def ensure_pip():

    try:

        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            check=True,
            capture_output=True,
        )

    except subprocess.CalledProcessError:

        print("[SETUP] pip is missing. Trying ensurepip...")

        try:

            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
            )

        except subprocess.CalledProcessError:

            print("[ERROR] Could not install pip automatically.")
            sys.exit(1)


def ensure_dependencies():

    print("\n" + "=" * 75)
    print("                 DEPENDENCY CHECK")
    print("=" * 75)

    ensure_pip()

    required_packages = {
        "huggingface_hub": "huggingface_hub",
    }

    for import_name, package_name in required_packages.items():

        if importlib.util.find_spec(import_name) is not None:

            print(f"[SKIP] {package_name} is already installed.")

            continue

        print(f"[INSTALL] Installing {package_name}...")

        try:

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    package_name,
                ],
                check=True,
            )

            print(f"[SUCCESS] {package_name} installed.")

        except subprocess.CalledProcessError as error:

            print(f"[ERROR] Dependency installation failed: {error}")
            sys.exit(1)


# Environment and dependencies must be ready before importing Hugging Face.
ensure_virtual_environment()
ensure_dependencies()

from huggingface_hub import snapshot_download
from huggingface_hub.utils import HfHubHTTPError


# ============================================================
# 4. MODEL CATALOGUE
# ============================================================

MODELS = {

    "1": {
        "name": "Qwen2.5 0.5B Instruct",
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "ram": "2-3 GB",
        "purpose": "Basic chat, simple document Q&A and RAG.",
        "notes": "Very lightweight. Good baseline for CPU testing.",
        "gated": False,
    },

    "2": {
        "name": "Qwen2.5 1.5B Instruct",
        "repo": "Qwen/Qwen2.5-1.5B-Instruct",
        "ram": "5-7 GB",
        "purpose": "General assistant and document-based Q&A.",
        "notes": "Good balance between response quality and resource usage.",
        "gated": False,
    },

    "3": {
        "name": "Qwen2.5 3B Instruct",
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "ram": "10-13 GB",
        "purpose": "Document understanding and reasoning.",
        "notes": "Heavier on CPU. Prefer a machine with 16 GB+ RAM.",
        "gated": False,
    },

    "4": {
        "name": "Qwen3.5 2B",
        "repo": "Qwen/Qwen3.5-2B",
        "ram": "8-11 GB",
        "purpose": "General assistant and newer-model experimentation.",
        "notes": "Check Transformers compatibility and architecture support.",
        "gated": False,
    },

    "5": {
        "name": "SmolLM2 360M Instruct",
        "repo": "HuggingFaceTB/SmolLM2-360M-Instruct",
        "ram": "1-2 GB",
        "purpose": "Simple chat, summarization and lightweight tasks.",
        "notes": "Suitable for low-memory CPU environments.",
        "gated": False,
    },

    "6": {
        "name": "SmolLM2 1.7B Instruct",
        "repo": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "ram": "6-8 GB",
        "purpose": "General chat and document Q&A.",
        "notes": "Useful for comparing compact models against Qwen.",
        "gated": False,
    },

    "7": {
        "name": "Llama 3.2 1B Instruct",
        "repo": "meta-llama/Llama-3.2-1B-Instruct",
        "ram": "4-5 GB",
        "purpose": "Lightweight assistant and basic RAG.",
        "notes": "Requires accepting Meta's model licence on Hugging Face.",
        "gated": True,
    },

    "8": {
        "name": "Llama 3.2 3B Instruct",
        "repo": "meta-llama/Llama-3.2-3B-Instruct",
        "ram": "10-13 GB",
        "purpose": "More capable general-purpose assistant.",
        "notes": "Requires accepting Meta's model licence on Hugging Face.",
        "gated": True,
    },

    "9": {
        "name": "TinyLlama 1.1B Chat",
        "repo": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "ram": "4-5 GB",
        "purpose": "Basic conversational tasks and experiments.",
        "notes": "Small and fast, but less capable than newer models.",
        "gated": False,
    },

    "10": {
        "name": "Phi-3.5 Mini Instruct",
        "repo": "microsoft/Phi-3.5-mini-instruct",
        "ram": "14-17 GB",
        "purpose": "Reasoning, instruction following and coding assistance.",
        "notes": "Relatively heavy for CPU inference. Prefer 16-32 GB RAM.",
        "gated": False,
    },

    "11": {
        "name": "Gemma 2 2B IT",
        "repo": "google/gemma-2-2b-it",
        "ram": "8-10 GB",
        "purpose": "General assistant, summarization and document Q&A.",
        "notes": "Requires accepting Google's Hugging Face model terms.",
        "gated": True,
    },
}


# ============================================================
# 5. MODEL UTILITIES
# ============================================================

def model_directory(model):

    return MODEL_DIR / model["repo"].split("/")[-1].lower()


def has_model_weights(path):

    weight_patterns = [
        "*.safetensors",
        "*.bin",
    ]

    for pattern in weight_patterns:

        if any(path.rglob(pattern)):
            return True

    return False


def is_installed(model):

    path = model_directory(model)

    config_exists = (path / "config.json").is_file()

    weights_exist = has_model_weights(path)

    return config_exists and weights_exist


def is_partially_downloaded(model):

    path = model_directory(model)

    return path.exists() and any(path.iterdir())


# ============================================================
# 6. DISPLAY MODEL CATALOGUE
# ============================================================

def display_models():

    print("\n" + "=" * 75)
    print("             KNOWLEDGEHUB AI - LOCAL LLM INSTALLER")
    print("=" * 75)

    for number, model in MODELS.items():

        if is_installed(model):
            status = "INSTALLED"

        elif is_partially_downloaded(model):
            status = "INCOMPLETE DOWNLOAD"

        else:
            status = "NOT INSTALLED"

        access = (
            " [HUGGING FACE ACCESS REQUIRED]"
            if model["gated"]
            else ""
        )

        print(f"\n[{number}] {model['name']} - {status}")

        print(f"    Repository : {model['repo']}")
        print(f"    RAM        : {model['ram']} (approx. FP32)")
        print(f"    Purpose    : {model['purpose']}")
        print(f"    Notes      : {model['notes']}{access}")

    print("\n" + "-" * 75)

    print("Enter model numbers separated by commas, e.g. 1,2,5")
    print("Enter 'all' to select every model.")
    print("Enter 'q' to quit.")

    print("-" * 75)


# ============================================================
# 7. MODEL SELECTION
# ============================================================

def parse_selection(selection):

    selection = selection.strip().lower()

    if selection == "all":

        return list(MODELS.keys())

    if selection == "q":

        return []

    selected = []

    for item in selection.split(","):

        item = item.strip()

        if item not in MODELS:

            raise ValueError(f"Invalid model selection: {item}")

        if item not in selected:

            selected.append(item)

    return selected


# ============================================================
# 8. HUGGING FACE AUTHENTICATION CHECK
# ============================================================

def check_authentication(model):

    if not model["gated"]:
        return True

    try:

        from huggingface_hub import HfApi

        HfApi().whoami()

        return True

    except Exception:

        print("\n[WARNING] Hugging Face authentication is unavailable.")

        print("If you have already accepted the model licence, authenticate with:")
        print("    hf auth login")

        print("You can also continue; the download will report an access error if needed.")

        return False


# ============================================================
# 9. DOWNLOAD WITH RETRIES
# ============================================================

def install_model(model):

    repo = model["repo"]
    destination = model_directory(model)

    if is_installed(model):

        print(f"\n[SKIP] {model['name']} is already installed.")
        print(f"       Location: {destination}")

        return True

    print(f"\n[DOWNLOAD] {model['name']}")
    print(f"Repository: {repo}")
    print(f"Destination: {destination}")

    check_authentication(model)

    destination.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):

        print(
            f"\n[ATTEMPT {attempt}/{MAX_DOWNLOAD_RETRIES}] "
            f"Downloading {model['name']}..."
        )

        try:

            snapshot_download(
                repo_id=repo,
                local_dir=str(destination),
            )

            if is_installed(model):

                print(f"\n[SUCCESS] {model['name']} downloaded.")

                return True

            print("[WARNING] Download returned, but model files are incomplete.")

        except HfHubHTTPError as error:

            print(f"\n[HUGGING FACE ERROR] {error}")

            if model["gated"]:

                print("\nThis model may require access approval.")

                print("1. Visit the model repository.")
                print("2. Accept its licence/access conditions.")
                print("3. Authenticate using: hf auth login")
                print("4. Run the installer again.")

                return False

        except Exception as error:

            print(f"\n[DOWNLOAD ERROR] {error}")

        if attempt < MAX_DOWNLOAD_RETRIES:

            print(f"[RETRY] Retrying in {RETRY_DELAY} seconds...")

            time.sleep(RETRY_DELAY)

    print(f"\n[FAILED] Could not complete download: {model['name']}")

    print("[INFO] Existing download files have been retained where possible.")
    print("[INFO] Run this installer again to retry.")

    return False


# ============================================================
# 10. INSTALLATION SUMMARY
# ============================================================

def display_summary(successful, failed):

    print("\n" + "=" * 75)
    print("                    INSTALLATION SUMMARY")
    print("=" * 75)

    print(f"\nSuccessful: {len(successful)}")

    for name in successful:

        print(f"  [OK] {name}")

    print(f"\nFailed: {len(failed)}")

    for name in failed:

        print(f"  [FAILED] {name}")

    print(f"\nPython environment: {sys.prefix}")
    print(f"Models directory  : {MODEL_DIR}")

    print("\nImportant:")

    print("- Models are downloaded, not automatically loaded.")
    print("- Model weights and configuration are checked before skipping.")
    print("- Incomplete downloads can be retried.")
    print("- Transformers and PyTorch are not installed by this downloader.")
    print("- Model loading compatibility must be checked separately.")


# ============================================================
# 11. MAIN
# ============================================================

def main():

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    display_models()

    selection = input("\nSelect models to install: ")

    try:

        selected = parse_selection(selection)

    except ValueError as error:

        print(f"\n[INVALID SELECTION] {error}")

        return

    if not selected:

        print("\nNo models selected. Exiting.")

        return

    print(f"\nSelected {len(selected)} model(s):")

    for number in selected:

        print(f"  - {MODELS[number]['name']}")

    confirm = input(
        "\nContinue with installation? (y/n): "
    ).strip().lower()

    if confirm not in ("y", "yes"):

        print("\nInstallation cancelled.")

        return

    successful = []
    failed = []

    for number in selected:

        model = MODELS[number]

        if install_model(model):

            successful.append(model["name"])

        else:

            failed.append(model["name"])

    display_summary(successful, failed)


if __name__ == "__main__":

    main()
