# Cramer Connect technical research

This documentation records the local investigation of integration version 0.8.1 and the Cramer Connect Android app, started on 11 November 2026. Its purpose is to support incremental contributions to the existing integration.

## Reading order

1. [Integration architecture and audit](ARCHITECTURE.md)
2. [Android application analysis](APK_ANALYSIS.md)
3. [Authentication and sessions](AUTHENTICATION.md)
4. [API and communication reference](API_REFERENCE.md)
5. [Feature comparison](FEATURE_GAP.md)
6. [Implementation roadmap](IMPLEMENTATION_PLAN.md)
7. [Open questions and verification](OPEN_QUESTIONS.md)
8. [Native lawn mower controls and manual checks](NATIVE_LAWN_MOWER_CONTROLS.md)

## Evidence levels

- **CONFIRMED IN CODE**: a declaration or call was found in the local integration or Android extraction. This does not prove current server acceptance.
- **INFERRED**: an interpretation supported by the code, with its basis stated.
- **PENDING REAL-WORLD VALIDATION**: requires sanitized responses or a separately authorized experiment.

Java paths are relative to `reverse_engineering/jadx/sources/`. Those files remain local and are deliberately excluded from Git, along with the APK and Apktool output. Line numbers refer to this extraction and may change between tool/app versions. Source references remain useful to someone with their own extraction; they are not public links to decompiled files.

## Scope and contribution boundaries

This branch contains documentation and ignore rules only. No integration or test changes and no root AGENTS.md are proposed here. Contributor guidance relevant to this investigation is included in the roadmap and verification documents. Native-control regression tests belong in a separate contribution.

No Cramer servers were contacted, no credentials were used, and no physical commands were sent during this work. The investigation is selective: it is not a complete backend specification or a certification of model compatibility. Application constants and real secrets are not reproduced.

The production-code consistency check and the contributor-reported Cramer RM1500 test scope are recorded in [Architecture](ARCHITECTURE.md#consistency-check-against-the-functional-integration). The repository README also lists the tested hardware.
