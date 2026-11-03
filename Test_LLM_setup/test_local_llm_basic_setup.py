
import gc
import os
from pathlib import Path

import torch

from transformers import AutoTokenizer, AutoModelForCausalLM


class LocalLLM:
    """
    Local Hugging Face LLM loader.

    Supports:
    - Qwen2.5
    - Qwen3.5
    - SmolLM2
    - Llama 3.2
    - TinyLlama
    - Phi-3.5
    - Gemma 2
    """

    def __init__(self, model_path: str, repo_id: str):

        self.model_path = Path(model_path)
        self.repo_id = repo_id

        self.model = None
        self.tokenizer = None
        self.processor = None

        self.is_qwen35 = "qwen3.5" in repo_id.lower()

        if not (self.model_path / "config.json").is_file():
            raise FileNotFoundError(
                f"Model configuration not found: {self.model_path}"
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Allow the user to configure CPU threads.
        cpu_threads = int(
            os.environ.get("LLM_CPU_THREADS", min(6, os.cpu_count() or 1))
        )

        torch.set_num_threads(max(1, cpu_threads))

        print("\n" + "=" * 60)
        print(f"Loading model: {repo_id}")
        print(f"Model path: {self.model_path}")
        print(f"Device: {self.device}")
        print(f"CPU threads: {torch.get_num_threads()}")
        print("=" * 60)

        self.load_model()

    # --------------------------------------------------------
    # MODEL LOADING
    # --------------------------------------------------------

    def load_model(self):

        dtype = (
            torch.float16
            if self.device == "cuda"
            else torch.float32
        )

        try:

            if self.is_qwen35:
                self.load_qwen35(dtype)

            else:
                self.load_causal_model(dtype)

            self.model.eval()

            print("\n[SUCCESS] Model loaded successfully.")

        except Exception as error:

            self.unload()

            raise RuntimeError(
                f"Could not load {self.repo_id}.\n"
                f"Check your Transformers version, model files, "
                f"available RAM and architecture compatibility.\n"
                f"Original error: {error}"
            ) from error

    def load_causal_model(self, dtype):

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            local_files_only=True,
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            local_files_only=True,
        )

        self.model.to(self.device)

    def load_qwen35(self, dtype):

        try:
            from transformers import (
                AutoProcessor,
                AutoModelForImageTextToText,
            )

        except ImportError as error:

            raise RuntimeError(
                "Your Transformers installation does not expose "
                "AutoModelForImageTextToText. Upgrade Transformers "
                "to a version supporting this model architecture."
            ) from error

        self.processor = AutoProcessor.from_pretrained(
            str(self.model_path),
            local_files_only=True,
        )

        self.model = AutoModelForImageTextToText.from_pretrained(
            str(self.model_path),
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            local_files_only=True,
        )

        self.model.to(self.device)

    # --------------------------------------------------------
    # INPUT PREPARATION
    # --------------------------------------------------------

    def prepare_inputs(self, prompt):

        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        if self.is_qwen35:

            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            )

        else:

            inputs = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            )

        inputs = {
            key: value.to(self.device)
            if isinstance(value, torch.Tensor)
            else value
            for key, value in inputs.items()
        }

        return inputs

    # --------------------------------------------------------
    # GENERATION
    # --------------------------------------------------------

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 128,
    ) -> str:

        if self.model is None:
            raise RuntimeError("Model is not loaded.")

        inputs = self.prepare_inputs(prompt)

        if "input_ids" not in inputs:
            raise RuntimeError(
                "Model inputs do not contain input_ids."
            )

        input_length = inputs["input_ids"].shape[-1]

        with torch.inference_mode():

            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        generated_tokens = outputs[0][input_length:]

        if self.is_qwen35:

            response = self.processor.batch_decode(
                generated_tokens.unsqueeze(0),
                skip_special_tokens=True,
            )[0]

        else:

            response = self.tokenizer.decode(
                generated_tokens,
                skip_special_tokens=True,
            )

        return response.strip()

    # --------------------------------------------------------
    # MEMORY CLEANUP
    # --------------------------------------------------------

    def unload(self):

        if self.model is not None:

            del self.model
            self.model = None

        if self.tokenizer is not None:

            del self.tokenizer
            self.tokenizer = None

        if self.processor is not None:

            del self.processor
            self.processor = None

        gc.collect()

        if torch.cuda.is_available():

            torch.cuda.empty_cache()

        print("[CLEANUP] Model resources released.")
