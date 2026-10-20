# Repository consolidation and publication

Keep source and frozen runners in their current import-compatible locations.
Use the root README as the entry point, current methodology/architecture docs
for interpretation, and the historical guides only for their own revisions.
Do not reformat frozen files while claiming their existing SHA checks still
apply. Preserve useful comments, raw outputs and assessment attribution.

`results/published/` is the deliberately selected publication tree. It includes
copies of saved review reports and selected original raw record files from
the matrix, direct baseline and direct confirmation. Selection manifests record
archive and file hashes. It is not every local uploaded session. Original
results remain untouched under ignored local folders.

The initial consolidation backs up replaced documentation/configuration to
`fix_backups/` and saves an installation report under `results/`. It does not
initialize Git, stage files, commit, push, publish, deploy, call models or
rewrite any generation pipeline. Run local software checks next, then inspect
the planned staging set and add the appropriate code license and notices.

Final hosting choice follows current free-tier resource checks and a separately
measured hosted smoke test. Semantic retrieval remains the same implementation;
the model, weight identity, dependency state and runtime must be documented
rather than presumed equivalent. A free static results page can be separate
from application compute. No provider is claimed supported at this stage.

Research references are linked in `references/README.md`. Full paper PDFs are
not bundled without an established redistribution basis. Citing a method does
not mean its training procedure or benchmark was reproduced.
