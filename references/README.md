# Research and source references

Papers are background and interpretation aids. EvidenceShift does not claim
to reproduce their training methods, datasets, metrics or benchmark results.

| Reference | Connection to this project | Boundary |
|---|---|---|
| Lewis et al. (2020), [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) | Retrieval plus generation | No end-to-end RAG model fine-tuning |
| Reimers and Gurevych (2019), [Sentence-BERT](https://arxiv.org/abs/1908.10084) | Sentence embeddings for semantic similarity | Uses a pretrained MiniLM SentenceTransformer; no SBERT training |
| Liu et al. (2023), [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) | Motivation to inspect context-position sensitivity | Simple order reversal here is not their benchmark or a causal replication |
| Gao et al. (2023), [Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/) | Distinguishing answer quality from citation support | No implementation of ALCE's full evaluation |
| [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Encoder used by shared local retrieval | A model name is not a pinned weight revision |

## Document provenance

Story fixtures and original real-document smoke tests use the simplified
*The Gift of the Magi*, O. Henry, from the U.S. Department of State American
English resource collection:
https://americanenglish.state.gov/files/ae/resource_files/1-the_gift_of_the_magi_0.pdf

Recorded original PDF SHA-256:
`cd4206e9dfc52aabb655b27e3935da81b18f244209e30f8304b249f9156b96c9`.
Document ID: `doc_90949049db10b9f640c8`. The parsed/indexed corpus has 19 chunks.
Saved evidence fixtures and records contain extracted text; PDF extraction
artifacts are preserved rather than silently corrected. The original PDF is
not added to this publication tree. Code licensing does not relicense source
documents, third-party libraries, models or research papers.

Fresh-policy fixtures and the Harbor Workshop confirmation manual are
fictional evaluation material. They are not real policies or external facts.
Full research PDFs are linked rather than bundled. Record provenance and
redistribution terms before adding any additional document to a public repo.
