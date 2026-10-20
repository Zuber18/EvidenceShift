# Research references

These papers provide background and evaluation ideas. EvidenceShift does not claim to reproduce their training procedures or benchmarks.

| Reference | Relevance | Implementation boundary |
|---|---|---|
| Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (2020), https://arxiv.org/abs/2005.11401 | Combining retrieval with generation for knowledge-intensive tasks | This project uses a document pipeline, not the paper's end-to-end fine-tuned RAG model |
| Reimers and Gurevych, *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks* (2019), https://arxiv.org/abs/1908.10084 | Sentence embeddings and cosine-based semantic comparison | The project uses the pre-trained MiniLM SentenceTransformer; it does not train SBERT |
| Gao et al., *Enabling Large Language Models to Generate Text with Citations* (2023), https://arxiv.org/abs/2305.14627 | Distinguishing answer quality and citation support | The current advisory checker is not a reproduction of the ALCE evaluation |

Extend this bibliography when a method is actually used or evaluated. Record source-document provenance separately from research references. Link to papers by default; add full PDFs only after checking redistribution permissions.
