from dataset_versioner.zenodo_client import ZenodoClient, ZenodoError  # noqa: D100


def main():  # noqa: ANN201, D103
    # Path to your CSV manifest
    manifest_path = (
        "/Users/shsingh/Documents/GitHub/datasets/manifests/profile_index.csv"
    )

    # Original deposition ID if updating an existing deposition
    original_id = "13892061"

    # Optional metadata
    metadata = {
        "metadata": {
            "title": "The Joint Undertaking for Morphological Profiling (JUMP) Consortium Datasets Index",
            "creators": [{"name": "The JUMP Cell Painting Consortium"}],
            "upload_type": "dataset",
            "access_right": "open",
        }
    }

    try:
        client = ZenodoClient()  # Ensure ZENODO_TOKEN is set in environment variables
        client.process_deposition(
            manifest_path=manifest_path, original_id=original_id, metadata=metadata
        )
    except ZenodoError as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
