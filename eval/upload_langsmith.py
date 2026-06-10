"""Upload the golden eval set to LangSmith as a reusable dataset.

Prerequisite env vars (in .env):
    LANGSMITH_API_KEY=ls__xxxxxxxx
    LANGSMITH_PROJECT=rag-lab-week4   (optional, for grouping traces)

Run:
    uv run python eval/upload_langsmith.py

Once uploaded, you can run LangSmith evaluators against this dataset and
compare experiments over time in the LangSmith UI.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from harness import load_golden  # type: ignore[import-not-found]

load_dotenv()

DATASET_NAME = os.getenv("LANGSMITH_DATASET", "rag-lab-golden")


def main() -> None:
    if not os.getenv("LANGSMITH_API_KEY"):
        print("ERROR: LANGSMITH_API_KEY not set in .env")
        sys.exit(1)

    from langsmith import Client  # imported here so the dep is optional

    client = Client()  # reads LANGSMITH_API_KEY from the environment
    golden = load_golden(subset=None)  # always upload the FULL set

    # Create the dataset if it doesn't already exist (idempotent-ish).
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        print(f"Using existing dataset '{DATASET_NAME}' ({dataset.id})")
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Hand-labeled SDN Q&A pairs for RAG evaluation.",
        )
        print(f"Created dataset '{DATASET_NAME}' ({dataset.id})")

    # Add each golden pair: inputs -> expected outputs, plus sliceable metadata.
    for ex in golden:
        client.create_example(
            inputs={"question": ex["question"]},
            outputs={"ground_truth": ex["ground_truth"]},
            dataset_id=dataset.id,
            metadata={
                "qtype": ex.get("qtype"),
                "source": ex.get("source_document"),
                "id": ex.get("id"),
            },
        )
    print(f"Uploaded {len(golden)} examples to LangSmith dataset '{DATASET_NAME}'.")


if __name__ == "__main__":
    main()
