"""Print the owner's messages and the failed tool calls of a Claude Code transcript.

Usage: python .claude/skills/retro/digest.py SESSION.jsonl [--width N]

A transcript is one JSON object per line. This keeps a retro from reading
megabytes of tool output: it prints only what the owner typed and every tool
result marked as an error, each cut to --width characters (default 300).
"""

import argparse
import json


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return ""


def digest(lines, width):
    tool_names = {}
    for number, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        if entry.get("type") == "assistant":
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_names[block.get("id")] = block.get("name", "?")
            continue
        if entry.get("type") != "user":
            continue
        failed = [
            b for b in blocks
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error")
        ]
        for block in failed:
            name = tool_names.get(block.get("tool_use_id"), "?")
            text = " ".join(text_of(block.get("content")).split())
            yield f"{number:>5} FAIL {name}: {text[:width]}"
        if not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
            text = " ".join(text_of(content).split())
            if text:
                yield f"{number:>5} OWNER: {text[:width]}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("transcript")
    parser.add_argument("--width", type=int, default=300)
    args = parser.parse_args()
    with open(args.transcript, encoding="utf-8") as handle:
        for row in digest(handle, args.width):
            print(row)


if __name__ == "__main__":
    main()
