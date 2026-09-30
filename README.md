# prompt-cache-auditor 🔍

> **Instant Prefix Invalidation & Token Cost Leak Detector for Multi-Turn AI Agents.**  
> Zero third-party dependencies. Pure Python 3 standard library.

---

## ⚡ The Problem
Prompt Caching (in Claude 3.7/3.5, OpenAI, DeepSeek) saves up to **90%** of input costs — **provided your prefix hash remains 100% byte-for-byte identical**.

However, many agent orchestration frameworks invisibly break prefix caching by:
1. Injecting dynamic timestamps or Run IDs into the system prompt header.
2. Reordering tool definitions based on user queries.
3. Mutating prompt guidelines between conversation turns.

A single mutated byte at the beginning shatters the KV cache prefix hash, forcing **full re-computation** and triggering **1.25x - 2.0x Cache Write penalties**.

---

## 🚀 Quick Start

Zero dependencies. Run with pure Python 3:

```bash
# Run the built-in real-world incident simulation
python3 prompt_cache_auditor.py --demo

# Audit two prompt files (Turn 1 vs Turn 2)
python3 prompt_cache_auditor.py --file1 turn1.txt --file2 turn2.txt --model claude-3-7-sonnet
```

---

## 📊 Terminal Visualization Output

```text
╔═══════════════════════════════════════════════════════════════════════╗
║             🔍 PROMPT CACHE PREFIX INVARIANCE AUDITOR                 ║
╚═══════════════════════════════════════════════════════════════════════╝
 Target Model: Claude 3.7 / 3.5 Sonnet

 Prefix Retention Rate: ██████░░░░░░░░░░░░░░░░░░░░░░░░░░ 19.5%

 🚨 CACHE MISS DETECTED (Prefix Invalidation):
    • First divergence at: Line 3, Column 29
    • Intact Cached Tokens: 30
    • Invalidated Tokens:   120 / 150 total

 📍 Divergence Point Anatomy:
    Turn 1: ...ter-US-East↵ Timestamp: 22:15:00 UTC...
    Turn 2: ...ter-US-East↵ Timestamp: 22:15:32 UTC...
                ▲ (Prefix Hash Shattered Here)

 💰 Financial Blast Radius (Per 1,000 Concurrent Calls):
    • Ideal Cache-Hit Cost:   $0.369
    • Actual Cache-Miss Cost: $0.562
    • Wasted Token Expense:    +$0.193 (+1.5x Inflation)

 🛠️  Engineering Fix / Refactor Rule:
    1. Move dynamic variables (timestamps, UUIDs, session counters) to the tail of prompt.
    2. Lock static rules, tool definitions, and system guidelines into a fixed binary prefix.
    3. Treat KV cache as read-only memory: Never mutate prefix bytes between multi-turn iterations.
─────────────────────────────────────────────────────────────────────────
```

---

## 🛠️ Pricing Models Supported
- **Claude 3.7 / 3.5 Sonnet** (Base $3.00, Cache Write $3.75, Cache Read $0.30)
- **Claude 3 / 3.5 Opus** (Base $15.00, Cache Write $18.75, Cache Read $1.50)
- **DeepSeek V3** (Base $0.27, Cache Read $0.07)
- **OpenAI GPT-4o** (Base $2.50, Cache Read $1.25)

---

## 📜 License
MIT License. Created by [@kiteciyuan48037](https://x.com/kiteciyuan48037).
