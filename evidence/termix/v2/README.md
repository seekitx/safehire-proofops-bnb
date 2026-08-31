# TermiX human-evidence workflow

The public `/benchmark` page is the capture tool. It deliberately does not create fake human evidence.

For each task, keep these files together:

1. The complete Agent output or downloaded live-hire receipt.
2. The timed `*-manual-output.json` from a real no-Agent run.
3. The `*-blind-review-packet.json` sent to the reviewer.
4. The private `*-blind-review-secret-key.json` retained by the preparer.
5. The completed `*-blind-review.json` returned by a named reviewer.

The reviewer should not be the person who prepared the packet. Do not reveal the secret key until the review JSON has been downloaded. A paid external Agent comparison should remain separate from sponsored SafeHire preview comparisons so cost claims stay honest.

After the reviewer returns the review file, merge the three matching artifacts:

```bash
python scripts/unblind_termix_review.py packet.json secret-key.json review.json --output unblinded-review.json
```
