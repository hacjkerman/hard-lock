# Hard Lock iOS cutoff editor and review fixes — Claude, 2026-09-27

All seven findings in `hard-lock-comprehensive-review-2026-09-27.md` are fixed on `worktree-ios-device-build`, with regression tests and the editor redesign. Package tests pass (94) and the unsigned device build succeeds. **Not installed, pushed or merged**; waiting for Codex review.

## Design

- **Overview.** One row per weekday: localized day name, a small tinted *Today* tag, the saved time (or *Off*) as the prominent value, *next morning* under after-midnight times, and an orange line for a scheduled change, e.g. *Turns off Tue 6:05 PM*. The saved value is always the one shown as current, so a queued Off never looks as if it had already disabled tonight's cutoff. A one-line footer gives the cooldown, or the commitment end date. Rows are single accessibility elements with full labels; at accessibility text sizes the row stacks vertically.
- **Day sheet.** *Now* and *Scheduled* (with activation time), a *Cutoff* switch and a wheel time picker, then one outcome line: applies now; **locks your phone now** (red, Save becomes *Save & Lock*); keeps the saved time and cancels the scheduled change; takes effect at a stated time after the wait (and whether it restarts an existing wait); blocked by commitment; or the reset hour is reserved. After-midnight times read *Friday night, early Saturday morning*. Cancel or swiping down discards the draft. Save is disabled when nothing would change.
- **Save.** `LockRules.decideSave` recomputes the outcome at the moment of Save. If it differs from what was shown, apart from the cooldown deadline moving with the clock, nothing is written and the sheet asks for a second Save. Otherwise `apply` runs once. A scheduled change can be withdrawn from the sheet with a confirmation, using the existing cancellation semantics.
- A day switched on starts its draft at 23:30. Unchanged drafts, including Off-then-On, save nothing. A day with a queued change opens at its scheduled value, so saving it unchanged leaves the queue and deadline alone.

## Findings

| # | Fix | Regression tests |
| --- | --- | --- |
| 1 P1 live picker persistence | Draft sheet (above); no bindings to `LockStore` | `CutoffDraftTests` (14), including the review's 18:00 → 10:30 → 22:30 sequence |
| 2 P1 03:59 cutoff skipped | Monitor judges each callback at its own edge (cutoff, reset, warning, pending maturity) when it arrives ≤60 s early, else at the actual time. No general look-ahead. | `MonitorBoundaryTests` (9): early, on-time, late, one-minute, reset, midnight reset, wrong weekday, pending wakeup |
| 3 P2 queued changes look like failed edits | Saved and scheduled shown separately with activation time; one Save per draft; restarts disclosed | `CutoffDraftTests`, `CutoffOverviewTests` (3) |
| 4 P2 stale commit/cancel | `commit` and new `cancelPending(key:now:)` start from `refreshPending(now:)` | `MutationFreshnessTests` (6): before, at, after maturity |
| 5 P2 status ignores authorization | `tonightStatus(authorized:now:)`; unauthorized shows *not enforced* | `TonightStatusTests` (4), matched against `shouldShield` |
| 6 P2 save vs enforcement | `ConfigPersistence.persist` returns `unchanged / saved / savedNotEnforced / notSaved`; messages say which; errors shown in the editor, the sheet and Pending changes. Failures still fail open. | `ConfigPersistenceTests` (5), incl. injected save and scheduler failures and a real unwritable store |
| 7 P3 redundant writes | Unchanged or rejected edits are neither saved nor re-armed; shields are cleared only when currently set | `testUnchangedConfigIsNeitherSavedNorRearmed` |

**Boundary policy tradeoff (finding 2).** The earlier rule evaluated every callback 60 seconds ahead, which skipped a one-minute lock entirely and also advanced unrelated callbacks. Now only a callback arriving up to 60 s before its own edge is treated as at that edge, so a lock can start at most 60 s early and a reset can release at most 60 s early — the same tolerance as before, applied narrowly. On-time and late callbacks agree exactly with the app's rules. Lock times and the cooldown/commitment policy are unchanged.

Existing monitor tests were rewritten for the callback-aware API with the same expectations. Activity names (`cutoff_HH_MM`, `pending_change`) are unchanged, so existing registrations stay valid.

## Changed files

- Kit: `LockRules.swift` (commit freshness, `cancelPending`, `MonitorActivity`, `MonitorCallback`, callback-aware monitor check; `calendar` now internal), new `CutoffEditing.swift` (draft, preview, save decision, day summaries, status, persistence outcome).
- App: `LockStore.swift`, `ScheduleManager.swift`, `MonitorExtension.swift`, `CutoffEditorView.swift` (rewritten), new `CutoffDaySheet.swift` and `CutoffFormat.swift`, `StatusView.swift`, `PendingChangesView.swift`.
- Tests: three new files; `RegressionTests.swift` and `FreshInstallTests.swift` updated for the monitor API.
- `ios/README.md`: editor, status, boundary behaviour; removed the stale reset-equal checklist item.

The config format is unchanged and no migration runs, so saved schedules load as before.

## Verification

| Check | Result |
| --- | --- |
| `swift test` in `ios/HardLockKit` on the Mac (README flags) | **94 tests, 0 failures** (53 before + 41 new) |
| `xcodebuild build`, Debug, `generic/platform=iOS`, `CODE_SIGNING_ALLOWED=NO`, Xcode 26.2 | **BUILD SUCCEEDED**, no Swift warnings, `HardLockMonitor.appex` embedded |
| `git diff --check` | clean |

Both ran from a temporary copy (`/tmp/hardlock-claude-0927`) and again in the Mac checkout after syncing the commit.

## Limits

- **No visual verification.** No simulator, preview or device render was made, so layout, spacing, Dynamic Type and VoiceOver are checked only by source and compile. Review them on the phone.
- View code (sheet flow, dismissal, error display) has no UI tests; the logic it calls is package-tested.
- Monitor callback delivery, early/late timing and shield ordering between the app and the extension still need the supervised device checklist.
- The new tests were written before the implementation and failed to compile against the old API; they were not separately run against the old rules. The review's reproduction script targets the removed `isLockedOutForMonitor(now:)` and no longer compiles.

## Next

Codex reviews `6305ea2..HEAD`. After approval, install with `ios/scripts/install-on-phone.sh` in the Mac's GUI session, then run the device checklist, starting with editing a day and cancelling, and a one-minute-before-reset cutoff.
