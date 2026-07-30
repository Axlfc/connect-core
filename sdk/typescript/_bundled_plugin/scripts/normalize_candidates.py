import json
import sys
import os

def normalize_candidates(input_path, output_path):
    """
    Validates candidates, deduplicates findings, and ensures standard format.
    """
    if not os.path.exists(input_path):
        print(f"Error: input path '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error: failed to parse json. {e}", file=sys.stderr)
        sys.exit(1)

    # Simple deduplication by fingerprint
    seen_fingerprints = set()
    deduped = []

    findings = data.get("findings", []) if isinstance(data, dict) else data
    for finding in findings:
        # Construct unique fingerprint
        cwe = finding.get("cwe", "CWE-Unknown")
        file_path = finding.get("file_path", "unknown")
        line = finding.get("line", 0)
        fingerprint = f"{cwe}:{file_path}:{line}"

        if fingerprint not in seen_fingerprints:
            seen_fingerprints.add(fingerprint)
            finding["fingerprint"] = fingerprint
            deduped.append(finding)

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"findings": deduped}, f, indent=2)

    print(f"Success: Normalized {len(deduped)} unique findings.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 normalize_candidates.py <input.json> <output.json>")
        sys.exit(1)
    normalize_candidates(sys.argv[1], sys.argv[2])
