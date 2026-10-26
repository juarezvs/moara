"""Explicit installation allowlist, independent of physical execution bindings."""
APPROVED={
    'gemma4-12b':{'tag':'gemma4:12b-it-q4_K_M','name':'Gemma 4 12B','category':'general','embedding':False},
    'qwen25-coder-7b':{'tag':'qwen2.5-coder:7b-instruct-q4_K_M','name':'Qwen 2.5 Coder 7B','category':'coding','embedding':False},
    'qwen3-embedding-06b':{'tag':'qwen3-embedding:0.6b','name':'Qwen 3 Embedding 0.6B','category':'embedding','embedding':True},
}
