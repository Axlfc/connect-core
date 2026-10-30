## 2025-02-17 - LRU Caching for System Prompt TOML and Tiktoken Encodings
**Learning:** Hot-path functions called on every LLM agent turn (such as loading prompt config TOML files and initializing tiktoken Encodings for token budget checks) create significant cumulative disk I/O and CPU overhead when left un-memoized.
**Action:** Always check if prompt loading and tokenizer initialization are cached with `@lru_cache` when profiling LLM orchestration layers.
