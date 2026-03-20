from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from groq import Groq

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from pdg.models import SectionDef


def analyze_section(section: SectionDef, csv_files: list[Path]) -> str:
    """Call Groq LLM to generate a technical analysis for *section*."""
    client = _get_client()
    csv_summary = _build_csv_summary(csv_files, section)
    system_msg, user_msg = _build_prompt(section, csv_summary)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


# ── internals ────────────────────────────────────────────────────────────────


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not found in environment or .env file. "
            "Get a free key at https://console.groq.com"
        )
    return Groq(api_key=api_key)


def _build_csv_summary(csv_files: list[Path], section: SectionDef) -> str:
    parts: list[str] = []
    for idx, path in enumerate(csv_files):
        df = pd.read_csv(path)
        label = path.name
        if section.loading_levels and idx < len(section.loading_levels):
            label = f"{path.name} ({section.loading_levels[idx]} loading)"

        if len(df) <= 100:
            text = df.to_string(index=False)
        else:
            head = df.head(20).to_string(index=False)
            tail = df.tail(10).to_string(index=False)
            desc = df.describe().to_string()
            text = (
                f"First 20 rows:\n{head}\n\n"
                f"Last 10 rows:\n{tail}\n\n"
                f"Statistical summary:\n{desc}"
            )
        parts.append(f"--- {label} ---\n{text}")
    return "\n\n".join(parts)


def _build_prompt(section: SectionDef, csv_summary: str) -> tuple[str, str]:
    system_msg = (
        "You are a senior power systems engineer writing analysis for a "
        "formal engineering report. Guidelines:\n"
        "- Use formal, technical tone appropriate for a utility compliance report\n"
        "- Reference actual measured values from the data\n"
        "- Compare against IEEE 519 limits where applicable\n"
        "- Identify trends across loading levels if multiple datasets are provided\n"
        "- State whether the results demonstrate compliance or non-compliance\n"
        "- Write 2-4 paragraphs of flowing prose\n"
        "- Do NOT include tables, charts, headings, or bullet points"
    )

    user_parts = [
        f"Section: {section.title}\n",
        f"Description: {section.description}\n",
    ]

    if section.ieee_limits:
        limits_str = ", ".join(f"H{k}: {v}%" for k, v in section.ieee_limits.items())
        user_parts.append(f"IEEE 519 Limits: {limits_str}\n")

    if section.loading_levels:
        user_parts.append(f"Loading levels: {', '.join(section.loading_levels)}\n")

    user_parts.append(f"Data:\n{csv_summary}\n")
    user_parts.append(
        "Write a technical analysis of this data for inclusion in the report."
    )

    return system_msg, "\n".join(user_parts)
