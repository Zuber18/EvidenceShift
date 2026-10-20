# Free deployment target

The installed demo now shares local MiniLM/Chroma retrieval. Deployment is pending validation; the previous lightweight TF-IDF deployment instructions are superseded.

1. Run the local software and real retrieval parity checks in `SEMANTIC_REVISION.md`.
2. Complete and review the local answer benchmark.
3. Push reviewed project code to GitHub. Keep secrets, private uploads, local databases, caches and raw runs excluded.
4. Try Streamlit Community Cloud with Python 3.12 and entrypoint `web_demo/app.py`. `web_demo/requirements.txt` contains the semantic stack dependencies. Verify model download, cold-start memory and a restart before calling this deployment supported.
5. Configure a Groq API key from a free-plan account in server-side Secrets, never in source code or chat:

```toml
GROQ_API_KEY = ""
```

6. Run the sample, non-sensitive PDF and DOCX checks, real inference and a saved ZIP download. Verify independent sessions and session clearing. Record actual models/profiles and provider requests.

No paid account upgrade, paid fallback or automatic retry is implemented. The provider account must remain on its free plan. Quotas and platform policies can change. The app's process-level budget is not durable billing enforcement and resets on restart.

Cloud model generation is distinct from local Ollama generation. Matching retrieval does not make a Groq run equivalent to the local Qwen benchmark. Do not expose a personal Ollama server publicly as an unreviewed workaround.

Official platform references:
- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/structured-outputs
- https://vercel.com/docs/functions/limitations

The project is not deployed by applying this patch. Account setup and real hosting validation remain outstanding.
