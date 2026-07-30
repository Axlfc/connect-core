import json
import csv
import sys
import os

def finalize_contract(input_path, output_sarif, output_csv):
    """
    Seals results and exports them to SARIF and CSV formats.
    """
    if not os.path.exists(input_path):
        print(f"Error: input '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    findings = data.get("findings", [])

    # 1. Export SARIF
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0-rtm.5.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Codex Security",
                    "version": "1.0.0",
                    "rules": []
                }
            },
            "results": []
        }]
    }

    rules_seen = set()
    for f in findings:
        rule_id = f.get("cwe", "CWE-Unknown")
        if rule_id not in rules_seen:
            rules_seen.add(rule_id)
            sarif["runs"][0]["tool"]["driver"]["rules"].append({
                "id": rule_id,
                "shortDescription": { "text": f.get("description", "Vulnerability") }
            })

        sarif["runs"][0]["results"].append({
            "ruleId": rule_id,
            "message": { "text": f.get("description", "Vulnerability details") },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": { "uri": f.get("file_path", "unknown") },
                    "region": { "startLine": f.get("line", 1) }
                }
            }]
        })

    os.makedirs(os.path.dirname(output_sarif), exist_ok=True)
    with open(output_sarif, 'w', encoding='utf-8') as sf:
        json.dump(sarif, sf, indent=2)

    # 2. Export CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, 'w', newline='', encoding='utf-8') as cf:
        writer = csv.writer(cf)
        writer.writerow(["cwe", "file_path", "line", "severity", "description"])
        for f in findings:
            writer.writerow([
                f.get("cwe", "CWE-Unknown"),
                f.get("file_path", "unknown"),
                f.get("line", 1),
                f.get("severity", "MEDIUM"),
                f.get("description", "")
            ])

    print(f"Success: Exported SARIF to '{output_sarif}' and CSV to '{output_csv}'.")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 finalize_scan_contract.py <input.json> <output.sarif> <output.csv>")
        sys.exit(1)
    finalize_contract(sys.argv[1], sys.argv[2], sys.argv[3])
