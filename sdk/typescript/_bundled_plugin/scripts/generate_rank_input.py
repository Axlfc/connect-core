import json
import sys
import os

def generate_partitions(input_path, output_dir, num_partitions=4):
    """
    Partitions normalized findings into multiple worklist files for parallel ranking or execution.
    """
    if not os.path.exists(input_path):
        print(f"Error: input '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    findings = data.get("findings", [])
    os.makedirs(output_dir, exist_ok=True)

    partitions = [[] for _ in range(num_partitions)]
    for idx, finding in enumerate(findings):
        partitions[idx % num_partitions].append(finding)

    for i, p in enumerate(partitions):
        part_path = os.path.join(output_dir, f"worklist_part_{i}.json")
        with open(part_path, 'w', encoding='utf-8') as f:
            json.dump({"findings": p}, f, indent=2)

    print(f"Success: Partitioned {len(findings)} findings into {num_partitions} files in '{output_dir}'.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 generate_rank_input.py <input.json> <output_dir> [num_partitions]")
        sys.exit(1)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    generate_partitions(sys.argv[1], sys.argv[2], n)
