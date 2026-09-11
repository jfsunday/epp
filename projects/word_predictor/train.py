#!/usr/bin/env python3
"""
Word Predictor MLP — Python training script.

Produces the exact same SQLite database as train.epp so that
predict.epp / predict_gui.epp can load and use the model.

Usage:
    python train.py                         # interactive
    python train.py sample_text.txt         # with file
    python train.py sample_text.txt -s 500  # 500 steps
    python train.py --help                  # all options
"""

import argparse
import math
import os
import random
import sqlite3
import sys
from collections import Counter


# ── Defaults (same as train.epp) ──────────────────────────────────────

DEFAULTS = dict(
    vocab_limit=50,
    whole_tokens=1,
    min_pair_count=1,
    context=2,
    embed_dim=4,
    hidden_dim=8,
    steps=100,
    batch_size=1,
    stop_mode="steps",
    learning_rate=0.01,
    target_loss=0.5,
    round_decimals=4,
    semantic_init=0,
    semantic_anchor="the",
    semantic_window=2,
    semantic_scale=0.1,
    target_coherence=0.0,
    coherence_weight=0.0,
    space_token=0,
)


# ── Vocabulary ────────────────────────────────────────────────────────

def build_vocab(text: str, cfg: dict) -> tuple[list[str], dict[str, int], list[int]]:
    """Tokenize text and build vocabulary. Returns (words, word2idx, token_ids).
    word2idx is 1-indexed to match E++ lists."""

    if cfg["whole_tokens"]:
        raw_tokens = text.split()
    else:
        raw_tokens = list(text)

    if cfg["space_token"] and cfg["whole_tokens"]:
        spaced = []
        for t in raw_tokens:
            spaced.append(t)
            spaced.append(" ")
        raw_tokens = spaced

    # Lowercase
    raw_tokens = [t.lower() for t in raw_tokens]

    # Frequency filter
    freq = Counter(raw_tokens)
    kept = [w for w, c in freq.most_common() if c >= cfg["min_pair_count"]]
    kept = kept[: cfg["vocab_limit"]]

    # Build mappings (1-indexed for E++ compatibility)
    words = kept  # index 0..len-1 in Python, but stored as 1..len
    word2idx = {w: i + 1 for i, w in enumerate(words)}

    # Encode tokens (skip OOV)
    token_ids = [word2idx[t] for t in raw_tokens if t in word2idx]

    return words, word2idx, token_ids


# ── Model ─────────────────────────────────────────────────────────────

class MLP:
    def __init__(self, vocab_sz: int, embed_dim: int, hidden_dim: int, context: int):
        self.vocab_sz = vocab_sz
        self.embed_dim = embed_dim
        self.hidden_dim = hidden_dim
        self.context = context
        self.input_dim = context * embed_dim

        # Xavier-ish random init
        e_scale = 1.0 / math.sqrt(embed_dim)
        h_scale = 1.0 / math.sqrt(self.input_dim)
        o_scale = 1.0 / math.sqrt(hidden_dim)

        self.embed = [[random.gauss(0, e_scale) for _ in range(embed_dim)]
                      for _ in range(vocab_sz)]
        self.hidden_w = [[random.gauss(0, h_scale) for _ in range(self.input_dim)]
                         for _ in range(hidden_dim)]
        self.hidden_b = [0.0] * hidden_dim
        self.out_w = [[random.gauss(0, o_scale) for _ in range(hidden_dim)]
                      for _ in range(vocab_sz)]
        self.out_b = [0.0] * vocab_sz

    def forward(self, ctx_tokens: list[int]) -> tuple[list[float], list[float], list[float]]:
        """Returns (probs, hidden_act, pre_act). ctx_tokens are 1-indexed."""
        # Embedding concat
        inp = []
        for tok in ctx_tokens:
            inp.extend(self.embed[tok - 1])

        # Hidden layer
        pre_act = []
        hidden_act = []
        for h in range(self.hidden_dim):
            s = sum(self.hidden_w[h][i] * inp[i] for i in range(self.input_dim))
            s += self.hidden_b[h]
            pre_act.append(s)
            hidden_act.append(max(0.0, s))  # ReLU

        # Output layer
        logits = []
        for o in range(self.vocab_sz):
            s = sum(self.out_w[o][h] * hidden_act[h] for h in range(self.hidden_dim))
            s += self.out_b[o]
            logits.append(s)

        # Softmax
        mx = max(logits)
        exps = [math.exp(l - mx) for l in logits]
        total = sum(exps)
        probs = [e / total for e in exps]

        return probs, hidden_act, pre_act, inp

    def backward(self, ctx_tokens: list[int], target_idx: int, lr: float,
                 probs: list[float], hidden_act: list[float],
                 pre_act: list[float], inp: list[float],
                 clip: float = 5.0):
        """Single-sample SGD update. target_idx is 1-indexed."""
        target = target_idx - 1  # 0-indexed

        def _clip(v):
            return max(-clip, min(clip, v))

        # Output gradient: softmax - one_hot
        d_out = list(probs)
        d_out[target] -= 1.0

        # Update output weights and bias
        for o in range(self.vocab_sz):
            g = _clip(d_out[o])
            for h in range(self.hidden_dim):
                self.out_w[o][h] -= lr * g * hidden_act[h]
            self.out_b[o] -= lr * g

        # Backprop to hidden
        d_hidden = [0.0] * self.hidden_dim
        for h in range(self.hidden_dim):
            for o in range(self.vocab_sz):
                d_hidden[h] += self.out_w[o][h] * d_out[o]
            # ReLU derivative
            if pre_act[h] <= 0:
                d_hidden[h] = 0.0
            d_hidden[h] = _clip(d_hidden[h])

        # Update hidden weights and bias
        for h in range(self.hidden_dim):
            for i in range(self.input_dim):
                self.hidden_w[h][i] -= lr * d_hidden[h] * inp[i]
            self.hidden_b[h] -= lr * d_hidden[h]

        # Update embeddings
        for ci, tok in enumerate(ctx_tokens):
            t = tok - 1
            offset = ci * self.embed_dim
            for d in range(self.embed_dim):
                grad = 0.0
                for h in range(self.hidden_dim):
                    grad += d_hidden[h] * self.hidden_w[h][offset + d]
                self.embed[t][d] -= lr * _clip(grad)

    def apply_semantic_init(self, token_ids: list[int], word2idx: dict,
                            anchor: str, window: int, scale: float):
        """Co-occurrence based embedding bias."""
        if anchor not in word2idx:
            print(f"  Semantic anchor '{anchor}' not in vocab, skipping.")
            return
        anchor_idx = word2idx[anchor]
        cooc = Counter()
        for i, tid in enumerate(token_ids):
            if tid == anchor_idx:
                for j in range(max(0, i - window), min(len(token_ids), i + window + 1)):
                    if j != i:
                        cooc[token_ids[j]] += 1
        for tid, count in cooc.items():
            bump = count * scale / self.embed_dim
            for d in range(self.embed_dim):
                self.embed[tid - 1][d] += bump
        print(f"  Semantic init applied (anchor='{anchor}', {len(cooc)} co-occurring tokens)")


# ── Training ──────────────────────────────────────────────────────────

def train(model: MLP, token_ids: list[int], cfg: dict) -> list[float]:
    """Train the model and return loss history."""
    ctx = cfg["context"]
    lr = cfg["learning_rate"]
    steps = cfg["steps"]
    batch_size = cfg["batch_size"]
    rd = cfg["round_decimals"]
    coh_wt = cfg["coherence_weight"]

    # Valid training positions: need ctx tokens before + 1 target
    if len(token_ids) < ctx + 1:
        print("ERROR: Not enough tokens for training.")
        return []

    positions = list(range(ctx, len(token_ids)))
    loss_history = []

    for step in range(1, steps + 1):
        epoch_loss = 0.0
        batch = random.choices(positions, k=batch_size)

        # Linear LR decay
        decay = 1.0 - 0.5 * (step - 1) / max(1, steps - 1)
        sample_lr = (lr * decay) / batch_size

        for pos in batch:
            ctx_tokens = token_ids[pos - ctx : pos]
            target = token_ids[pos]

            probs, hidden_act, pre_act, inp = model.forward(ctx_tokens)

            # Cross-entropy loss (before update)
            p = max(probs[target - 1], 1e-7)
            loss = -math.log(p)
            epoch_loss += loss

            model.backward(ctx_tokens, target, sample_lr, probs, hidden_act, pre_act, inp)

        epoch_loss /= batch_size

        # Coherence penalty
        if coh_wt > 0:
            coh = compute_coherence(model, token_ids, ctx)
            epoch_loss += (1.0 - coh) * coh_wt
        else:
            coh = None

        loss_history.append(epoch_loss)

        # Progress
        if step % max(1, steps // 20) == 0 or step == 1 or step == steps:
            coh_str = f"  coh={coh:.{rd}f}" if coh is not None else ""
            print(f"  step {step:>{len(str(steps))}}/{steps}  "
                  f"loss={epoch_loss:.{rd}f}{coh_str}")

        # Early stopping
        if cfg["stop_mode"] == "loss" and epoch_loss <= cfg["target_loss"]:
            print(f"  Reached target loss {cfg['target_loss']} at step {step}.")
            break
        if cfg["target_coherence"] > 0 and coh is not None and coh >= cfg["target_coherence"]:
            print(f"  Reached target coherence {cfg['target_coherence']} at step {step}.")
            break

    return loss_history


def compute_coherence(model: MLP, token_ids: list[int], ctx: int,
                      max_checks: int = 50) -> float:
    """Measure argmax accuracy on random positions."""
    positions = list(range(ctx, len(token_ids)))
    if not positions:
        return 0.0
    checks = random.sample(positions, min(max_checks, len(positions)))
    matches = 0
    for pos in checks:
        ctx_tokens = token_ids[pos - ctx : pos]
        probs, _, _, _ = model.forward(ctx_tokens)
        predicted = probs.index(max(probs)) + 1  # 1-indexed
        if predicted == token_ids[pos]:
            matches += 1
    return matches / len(checks)


# ── Database save ─────────────────────────────────────────────────────

def save_to_db(model: MLP, words: list[str], word2idx: dict[str, int],
               cfg: dict, loss_history: list[float], db_path: str):
    """Save model to SQLite in the exact format E++ predict scripts expect."""
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables (all TEXT columns, matching E++)
    c.execute('CREATE TABLE "vocab" ("word" TEXT, "idx" TEXT)')
    c.execute('CREATE TABLE "config" ("key" TEXT, "val" TEXT)')
    c.execute('CREATE TABLE "embeddings" ("pos" TEXT, "val" TEXT)')
    c.execute('CREATE TABLE "hiddenw" ("pos" TEXT, "val" TEXT)')
    c.execute('CREATE TABLE "hiddenb" ("pos" TEXT, "val" TEXT)')
    c.execute('CREATE TABLE "outputw" ("pos" TEXT, "val" TEXT)')
    c.execute('CREATE TABLE "outputb" ("pos" TEXT, "val" TEXT)')

    # Vocab (1-indexed)
    for word, idx in word2idx.items():
        c.execute('INSERT INTO vocab VALUES (?, ?)', (word, str(idx)))

    # Config
    input_dim = model.context * model.embed_dim
    final_loss = loss_history[-1] if loss_history else 0.0
    config_entries = [
        ("vocabsize", str(model.vocab_sz)),
        ("context", str(model.context)),
        ("embeddim", str(model.embed_dim)),
        ("hiddendim", str(model.hidden_dim)),
        ("inputdim", str(input_dim)),
        ("steps", str(len(loss_history))),
        ("learnrate", str(cfg["learning_rate"])),
        ("finalloss", str(round(final_loss, cfg["round_decimals"]))),
    ]
    for k, v in config_entries:
        c.execute('INSERT INTO config VALUES (?, ?)', (k, v))

    # Embeddings: flat list, 1-indexed pos
    pos = 1
    for tok_emb in model.embed:
        for val in tok_emb:
            c.execute('INSERT INTO embeddings VALUES (?, ?)', (str(pos), str(val)))
            pos += 1

    # Hidden weights: flat [hidden_dim × input_dim], row-major, 1-indexed
    pos = 1
    for row in model.hidden_w:
        for val in row:
            c.execute('INSERT INTO hiddenw VALUES (?, ?)', (str(pos), str(val)))
            pos += 1

    # Hidden bias
    for i, val in enumerate(model.hidden_b):
        c.execute('INSERT INTO hiddenb VALUES (?, ?)', (str(i + 1), str(val)))

    # Output weights: flat [vocab_sz × hidden_dim], row-major, 1-indexed
    pos = 1
    for row in model.out_w:
        for val in row:
            c.execute('INSERT INTO outputw VALUES (?, ?)', (str(pos), str(val)))
            pos += 1

    # Output bias
    for i, val in enumerate(model.out_b):
        c.execute('INSERT INTO outputb VALUES (?, ?)', (str(i + 1), str(val)))

    conn.commit()
    conn.close()


# ── Prediction helper ─────────────────────────────────────────────────

def generate(model: MLP, words: list[str], word2idx: dict[str, int],
             seed: str, count: int) -> str:
    """Generate text starting from seed word."""
    seed = seed.lower()
    if seed not in word2idx:
        return f"Unknown word: '{seed}'"

    seed_idx = word2idx[seed]
    history = [seed_idx] * model.context
    result = [seed]

    for _ in range(count):
        ctx_tokens = history[-model.context:]
        probs, _, _, _ = model.forward(ctx_tokens)
        best = probs.index(max(probs)) + 1
        result.append(words[best - 1])
        history.append(best)

    return " ".join(result)


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Train a word predictor MLP (same DB format as E++ train.epp)")
    parser.add_argument("textfile", nargs="?", help="Training text file")
    parser.add_argument("-t", "--text", help="Training text string (inline)")
    parser.add_argument("-v", "--vocab-limit", type=int, default=DEFAULTS["vocab_limit"])
    parser.add_argument("--whole-tokens", type=int, default=DEFAULTS["whole_tokens"],
                        choices=[0, 1], help="1=words, 0=characters")
    parser.add_argument("--min-pairs", type=int, default=DEFAULTS["min_pair_count"])
    parser.add_argument("-c", "--context", type=int, default=DEFAULTS["context"])
    parser.add_argument("-e", "--embed-dim", type=int, default=DEFAULTS["embed_dim"])
    parser.add_argument("-H", "--hidden-dim", type=int, default=DEFAULTS["hidden_dim"])
    parser.add_argument("-s", "--steps", type=int, default=DEFAULTS["steps"])
    parser.add_argument("-b", "--batch-size", type=int, default=DEFAULTS["batch_size"])
    parser.add_argument("--stop-mode", choices=["steps", "loss"], default=DEFAULTS["stop_mode"])
    parser.add_argument("-l", "--learning-rate", type=float, default=DEFAULTS["learning_rate"])
    parser.add_argument("--target-loss", type=float, default=DEFAULTS["target_loss"])
    parser.add_argument("--round-decimals", type=int, default=DEFAULTS["round_decimals"])
    parser.add_argument("--semantic-init", type=int, choices=[0, 1], default=DEFAULTS["semantic_init"])
    parser.add_argument("--semantic-anchor", default=DEFAULTS["semantic_anchor"])
    parser.add_argument("--semantic-window", type=int, default=DEFAULTS["semantic_window"])
    parser.add_argument("--semantic-scale", type=float, default=DEFAULTS["semantic_scale"])
    parser.add_argument("--target-coherence", type=float, default=DEFAULTS["target_coherence"])
    parser.add_argument("--coherence-weight", type=float, default=DEFAULTS["coherence_weight"])
    parser.add_argument("--space-token", type=int, choices=[0, 1], default=DEFAULTS["space_token"])
    parser.add_argument("-o", "--output", default="word predictor.db",
                        help="Output DB path (default: 'word predictor.db')")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("-g", "--generate", metavar="WORD",
                        help="After training, generate text starting from WORD")
    parser.add_argument("--gen-count", type=int, default=10,
                        help="Number of words to generate (default: 10)")

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # Load text
    if args.textfile:
        with open(args.textfile) as f:
            text = f.read().strip()
    elif args.text:
        text = args.text.strip()
    else:
        print("Enter training text (Ctrl+D to finish):")
        text = sys.stdin.read().strip()

    if not text:
        print("ERROR: No training text provided.")
        sys.exit(1)

    cfg = {
        "vocab_limit": args.vocab_limit,
        "whole_tokens": args.whole_tokens,
        "min_pair_count": args.min_pairs,
        "context": args.context,
        "embed_dim": args.embed_dim,
        "hidden_dim": args.hidden_dim,
        "steps": args.steps,
        "batch_size": args.batch_size,
        "stop_mode": args.stop_mode,
        "learning_rate": args.learning_rate,
        "target_loss": args.target_loss,
        "round_decimals": args.round_decimals,
        "semantic_init": args.semantic_init,
        "semantic_anchor": args.semantic_anchor,
        "semantic_window": args.semantic_window,
        "semantic_scale": args.semantic_scale,
        "target_coherence": args.target_coherence,
        "coherence_weight": args.coherence_weight,
        "space_token": args.space_token,
    }

    # Build vocab
    print(f"Building vocabulary...")
    words, word2idx, token_ids = build_vocab(text, cfg)
    vocab_sz = len(words)
    print(f"  Vocab: {vocab_sz} tokens, {len(token_ids)} total tokens in corpus")
    if vocab_sz < 2:
        print("ERROR: Vocabulary too small (need at least 2 tokens).")
        sys.exit(1)

    # Init model
    model = MLP(vocab_sz, cfg["embed_dim"], cfg["hidden_dim"], cfg["context"])
    total_params = (vocab_sz * cfg["embed_dim"]
                    + cfg["hidden_dim"] * model.input_dim + cfg["hidden_dim"]
                    + vocab_sz * cfg["hidden_dim"] + vocab_sz)
    print(f"  Model: embed={cfg['embed_dim']}, hidden={cfg['hidden_dim']}, "
          f"ctx={cfg['context']}, params={total_params}")

    # Semantic init
    if cfg["semantic_init"]:
        model.apply_semantic_init(token_ids, word2idx,
                                  cfg["semantic_anchor"],
                                  cfg["semantic_window"],
                                  cfg["semantic_scale"])

    # Train
    print(f"Training ({cfg['steps']} steps, batch={cfg['batch_size']}, lr={cfg['learning_rate']})...")
    loss_history = train(model, token_ids, cfg)

    if loss_history:
        print(f"  Final loss: {loss_history[-1]:.{cfg['round_decimals']}f}")
        coh = compute_coherence(model, token_ids, cfg["context"])
        print(f"  Final coherence: {coh:.{cfg['round_decimals']}f}")

    # Save
    db_path = args.output
    save_to_db(model, words, word2idx, cfg, loss_history, db_path)
    print(f"Saved to {db_path}")

    # Generate
    if args.generate:
        print(f"\nGeneration (seed='{args.generate}', count={args.gen_count}):")
        result = generate(model, words, word2idx, args.generate, args.gen_count)
        print(f"  {result}")
    else:
        # Quick demo with first vocab word
        demo_word = words[0] if words else None
        if demo_word:
            result = generate(model, words, word2idx, demo_word, 8)
            print(f"\nDemo: {result}")


if __name__ == "__main__":
    main()
