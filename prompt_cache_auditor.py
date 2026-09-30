#!/usr/bin/env python3
"""
prompt-cache-auditor: Instant Prefix Invalidation & Token Cost Leak Detector for AI Agents.
Zero dependencies. Pure Python 3.

Features:
- Diffs multi-turn Agent system/user prompts to find the EXACT byte/token that broke KV cache prefix hash
- Calculates financial cost leak (Cache Hit @ 0.1x vs Cache Miss/Write @ 1.25x-2.0x)
- Supports Claude, OpenAI, and DeepSeek pricing models
- Renders terminal ASCII visual prefix breakdown with actionable refactoring advice
"""

import sys
import json
import difflib
import argparse
from typing import List, Dict, Tuple, Optional

# Color codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

# Model pricing standards (Base Input per M, Cache Write per M, Cache Read per M)
MODEL_PRICING = {
    "claude-3-7-sonnet": {
        "name": "Claude 3.7 / 3.5 Sonnet",
        "base_input": 3.00,
        "cache_write_5m": 3.75,   # 1.25x
        "cache_read": 0.30        # 0.1x (90% discount)
    },
    "claude-3-opus": {
        "name": "Claude 3 / 3.5 Opus",
        "base_input": 15.00,
        "cache_write_5m": 18.75,  # 1.25x
        "cache_read": 1.50        # 0.1x
    },
    "deepseek-v3": {
        "name": "DeepSeek V3",
        "base_input": 0.27,
        "cache_write_5m": 0.27,
        "cache_read": 0.07        # ~74% discount
    },
    "gpt-4o": {
        "name": "OpenAI GPT-4o",
        "base_input": 2.50,
        "cache_write_5m": 2.50,
        "cache_read": 1.25        # 50% discount
    }
}


def find_longest_common_prefix(s1: str, s2: str) -> Tuple[int, int, int]:
    """Returns (prefix_length, line_num, col_num) where diff first occurs."""
    min_len = min(len(s1), len(s2))
    idx = 0
    line = 1
    col = 1
    while idx < min_len and s1[idx] == s2[idx]:
        if s1[idx] == '\n':
            line += 1
            col = 1
        else:
            col += 1
        idx += 1
    return idx, line, col


def estimate_tokens(text: str) -> int:
    """Rough heuristic: 1 token ~ 3.8 English chars or 1.5 Chinese chars."""
    if not text:
        return 0
    # count non-ascii (like CJK)
    cjk = sum(1 for c in text if ord(c) > 127)
    ascii_chars = len(text) - cjk
    return int((ascii_chars / 3.8) + (cjk / 1.5)) + 1


def render_progress_bar(ratio: float, width: int = 32) -> str:
    filled = int(width * ratio)
    empty = width - filled
    bar = f"{GREEN}{'█' * filled}{RED}{'░' * empty}{RESET}"
    return bar


def audit_prompts(prompt_a: str, prompt_b: str, model_key: str = "claude-3-7-sonnet") -> dict:
    pricing = MODEL_PRICING.get(model_key, MODEL_PRICING["claude-3-7-sonnet"])
    
    total_len = max(len(prompt_a), len(prompt_b))
    prefix_len, line_num, col_num = find_longest_common_prefix(prompt_a, prompt_b)
    
    match_ratio = (prefix_len / total_len) if total_len > 0 else 1.0
    
    tokens_a = estimate_tokens(prompt_a)
    tokens_b = estimate_tokens(prompt_b)
    tokens_prefix = estimate_tokens(prompt_a[:prefix_len])
    tokens_invalidated = max(0, tokens_b - tokens_prefix)
    
    # Calculate costs
    # Scenario 1: Optimal (Prefix is preserved, rest is read from cache)
    cost_optimal = (tokens_prefix / 1_000_000) * pricing["cache_read"] + \
                   (tokens_invalidated / 1_000_000) * pricing["base_input"]
                   
    # Scenario 2: Actual / Cache Miss (Prefix broken -> full cache write penalty or full input)
    cost_actual = (tokens_b / 1_000_000) * pricing["cache_write_5m"]
    
    cost_waste_multiplier = (cost_actual / cost_optimal) if cost_optimal > 0 else 1.0
    cost_delta = max(0.0, cost_actual - cost_optimal)
    
    # Extract snippet of invalidation
    start_ctx = max(0, prefix_len - 40)
    end_ctx_a = min(len(prompt_a), prefix_len + 40)
    end_ctx_b = min(len(prompt_b), prefix_len + 40)
    
    diff_snippet_a = prompt_a[start_ctx:end_ctx_a].replace("\n", "↵ ")
    diff_snippet_b = prompt_b[start_ctx:end_ctx_b].replace("\n", "↵ ")
    
    return {
        "model": pricing["name"],
        "total_chars_a": len(prompt_a),
        "total_chars_b": len(prompt_b),
        "prefix_len": prefix_len,
        "line_num": line_num,
        "col_num": col_num,
        "match_ratio": match_ratio,
        "tokens_b": tokens_b,
        "tokens_prefix": tokens_prefix,
        "tokens_invalidated": tokens_invalidated,
        "cost_optimal": cost_optimal,
        "cost_actual": cost_actual,
        "cost_waste_multiplier": cost_waste_multiplier,
        "cost_delta": cost_delta,
        "diff_snippet_a": diff_snippet_a,
        "diff_snippet_b": diff_snippet_b
    }


def print_audit_report(res: dict):
    print(f"\n{BOLD}{CYAN}╔═══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║             🔍 PROMPT CACHE PREFIX INVARIANCE AUDITOR                 ║{RESET}")
    print(f"{BOLD}{CYAN}╚═══════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f" {DIM}Target Model:{RESET} {BOLD}{res['model']}{RESET}")
    
    pct = res['match_ratio'] * 100
    bar = render_progress_bar(res['match_ratio'])
    print(f"\n {BOLD}Prefix Retention Rate:{RESET} {bar} {BOLD}{pct:.1f}%{RESET}")
    
    if res['match_ratio'] >= 0.999:
        print(f"\n {GREEN}✅ SUCCESS: Prefix hash is 100% INTACT.{RESET}")
        print(f"    KV Cache Read hit expected across calls.")
        return

    print(f"\n {RED}{BOLD}🚨 CACHE MISS DETECTED (Prefix Invalidation):{RESET}")
    print(f"    • First divergence at: {BOLD}Line {res['line_num']}, Column {res['col_num']}{RESET}")
    print(f"    • Intact Cached Tokens: {GREEN}{res['tokens_prefix']:,}{RESET}")
    print(f"    • Invalidated Tokens:   {RED}{res['tokens_invalidated']:,}{RESET} / {res['tokens_b']:,} total")
    
    print(f"\n {BOLD}📍 Divergence Point Anatomy:{RESET}")
    print(f"    {YELLOW}Turn 1:{RESET} ...{res['diff_snippet_a']}...")
    print(f"    {RED}Turn 2:{RESET} ...{res['diff_snippet_b']}...")
    print(f"             {' ' * 3}{RED}▲ (Prefix Hash Shattered Here){RESET}")
    
    print(f"\n {BOLD}💰 Financial Blast Radius (Per 1,000 Concurrent Calls):{RESET}")
    print(f"    • Ideal Cache-Hit Cost:   {GREEN}${res['cost_optimal'] * 1000:.3f}{RESET}")
    print(f"    • Actual Cache-Miss Cost: {RED}${res['cost_actual'] * 1000:.3f}{RESET}")
    print(f"    • {BOLD}Wasted Token Expense:{RESET}    {RED}{BOLD}+${res['cost_delta'] * 1000:.3f} (+{res['cost_waste_multiplier']:.1f}x Inflation){RESET}")
    
    print(f"\n {BOLD}🛠️  Engineering Fix / Refactor Rule:{RESET}")
    print(f"    1. Move dynamic variables (timestamps, UUIDs, session counters) to the {BOLD}tail of prompt{RESET}.")
    print(f"    2. Lock static rules, tool definitions, and system guidelines into a {BOLD}fixed binary prefix{RESET}.")
    print(f"    3. Treat KV cache as read-only memory: Never mutate prefix bytes between multi-turn iterations.")
    print(f"{CYAN}─────────────────────────────────────────────────────────────────────────{RESET}\n")


def run_demo():
    print(f"{DIM}[Running Built-in Real-World Incident Simulation...]{RESET}")
    # Simulating a real production gotcha: injecting dynamic timestamp at the top of system instructions
    prompt_turn_1 = """[System Instruction: Production Agent v2.4]
Environment: Production-Cluster-US-East
Timestamp: 2026-09-30 22:15:00 UTC
Guidelines:
1. You are a senior site reliability engineer assisting with Kubernetes cluster diagnostics.
2. Adhere strictly to the read-only inspection protocol: never execute mutating kubectl commands.
3. Verify cluster topology before inspecting pod events.
[Schema & Tools]
tool: get_pod_logs(namespace: str, pod_name: str, tail_lines: int)
tool: inspect_ingress(ingress_name: str)
[User Query]
Please list all unhealthy pods in the default namespace."""

    prompt_turn_2 = """[System Instruction: Production Agent v2.4]
Environment: Production-Cluster-US-East
Timestamp: 2026-09-30 22:15:32 UTC
Guidelines:
1. You are a senior site reliability engineer assisting with Kubernetes cluster diagnostics.
2. Adhere strictly to the read-only inspection protocol: never execute mutating kubectl commands.
3. Verify cluster topology before inspecting pod events.
[Schema & Tools]
tool: get_pod_logs(namespace: str, pod_name: str, tail_lines: int)
tool: inspect_ingress(ingress_name: str)
[User Query]
Please inspect logs of pod coredns-7c65d6cfc9-2j4x8."""

    res = audit_prompts(prompt_turn_1, prompt_turn_2, "claude-3-7-sonnet")
    print_audit_report(res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit Prompt Caching prefix validity between multi-turn agent calls")
    parser.add_argument("--demo", action="store_true", help="Run real-world demonstration")
    parser.add_argument("--file1", help="Path to first prompt text or JSON")
    parser.add_argument("--file2", help="Path to second prompt text or JSON")
    parser.add_argument("--model", default="claude-3-7-sonnet", choices=list(MODEL_PRICING.keys()), help="Model pricing profile")
    args = parser.parse_args()

    if args.demo or (not args.file1 and not args.file2):
        run_demo()
    else:
        with open(args.file1, "r", encoding="utf-8") as f:
            p1 = f.read()
        with open(args.file2, "r", encoding="utf-8") as f:
            p2 = f.read()
        res = audit_prompts(p1, p2, args.model)
        print_audit_report(res)
