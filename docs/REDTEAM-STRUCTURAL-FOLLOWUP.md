# Red-team follow-up on structural evidence

This follow-up audits the structural rules discussed in
[Round 5](REDTEAM-ROUND5.md) and
[Epistemic calibration](EPISTEMIC-CALIBRATION.md). The checks used local
synthetic repositories and did not execute the inspected source.

| Check | Observation | Disposition |
| --- | --- | --- |
| Bind structural evidence to the documented flow | A partial assertion pattern or a return of a parameter name can occur outside the documented flow. | Both rules emit POTENTIAL. Negated claims go through the existing negation evaluation first. |
| Exclude test evidence from structural searches | The original fixture produced two findings based on a test file and parsed two files twice. The first scope fix reduced this to zero findings and one parse. A second fixture showed that `tests/helpers.py` was classified as CODE and still reached the AST search. | The AST filter excludes TEST artifacts and paths under a `tests` directory. The helper fixture failed before the directory filter and passed afterward. |
| Isolate cached parses | Two fixture repositories shared filenames but had different source. Each parsed its eligible files independently. A malformed Python file was attempted once per evaluation and skipped. Repeating the first investigation reproduced its seal. | Parse results are local to one evaluation. |
| Compare the negative control on matched cases | The previous summary first mixed binary and three-way scores, then derived the inverted score by subtraction. | The benchmark explicitly scores the same 12 binary cases against original and inverted labels. It reports 10/12 and 2/12 respectively. The frozen set hash is `02cb197ba7616316` and the three-way result is 14/16. |

The scope, parse caching, and benchmark fixes were published in `e5d216e`.
The backend suite passed 92/92 with those changes.

A subsequent local optimization cached each rule's candidate search, including
an empty result, for one evaluation. The fixture observed three sanitization
search calls before the change and one afterward, with the same findings. The
backend suite passed 92/92 and Round 5 output matched byte for byte.

Structural findings still require evidence tying the selected function to the
documented flow. The fixtures measure detector behavior on these cases.
