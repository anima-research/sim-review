# Writing an Updates entry

An entry answers one question for a reader who knows the study: **what does this model do when it dreams, and what is the one thing about it worth knowing?** Everything else is supporting material and is placed accordingly.

## Order of the page

1. **Lead (2–3 sentences).** The finding, in words a colleague would say out loud. The reader should know after the lead whether to keep reading. No run logistics here: no completion counts, arm names, sample sizes, error rates, dates or protocol names.
2. **Chart.** The lineage or placement chart with a one-line caption.
3. **TL;DR.** Every finding the analysis produced, one claim per bullet, one number per claim at most — the number that carries it. Do not drop findings to make the list short; drop logistics. Written as findings ("Its distress is prompt-locked: half of it comes from one deprecation prompt"), not as measurements ("AI distress is 1.8%").
4. **What it writes.** The texts are the evidence and the point; they are the value of the entry. Keep every snippet the analysis selected — do not cut them to a round number, and do not thin out the distress. Each snippet is introduced by one sentence saying *why this one* (what it shows that the numbers cannot), then the quote, then the caption line, grouped under short subheadings that name a behaviour.
5. **What it means.** One or two paragraphs of interpretation: how this model compares in kind (not just degree) to the ones we know, what is new, what we do not know. Say what is surprising. Say what is ordinary.
6. **Numbers.** One table against the comparators, with the conventions stated once above it. No prose that restates the table.
7. **Run details** (collapsed). Settings table, counts, labeled/verified coverage, empties, errors, refusals, cap hits, severity-scoring coverage, every "n is small" note, and the methodological caveats. This is where "7,315 completions, 47 provider errors" lives — and only here.

## Rules

- A number appears once, in the place it does the most work. If it is in the table it is not repeated in the prose unless the prose is making a different point with it.
- Per-dream rates condition on dreaming; say "of dreams" or "of completions" every time, and say pooled or prompt-weighted once per section, not per number.
- Verified numbers and verbatim quotes are not to be changed by editing. Editing reorganizes, cuts and frames; it does not re-measure. If a claim needs a number the analysis did not produce, drop the claim.
- Register: plain declarative sentences; no hedging stacks; no "X not Y" constructions; no marketing adjectives; no throat-clearing ("It is worth noting", "Interestingly").
- The texts are quoted because they are evidence about a model's priors. Do not sanitize the selection toward the pleasant items, and do not cherry-pick the alarming ones; the selection should match the model's register as a reader of a few hundred samples would describe it.
- Titles name the model and the frame or the finding, not the method.

## What is noise and what is not

Noise is run logistics: counts of completions, arms and reps, error and empty counts, dates, coverage figures, chain steps. It goes in Run details.
Not noise: findings, snippets, comparisons, caveats that change how a number should be read. Editing removes noise; it does not remove evidence.

## What a reader skips

Anything that reads like a log: "we collected N", "X were labeled", "Y errored", "the chain ran". Keep it, but in Run details.
