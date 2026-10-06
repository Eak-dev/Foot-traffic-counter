# PROJECT_CONTROL — FT-D0

Owner direction dated 2026-10-06 supersedes the Raspberry Pi/live-RTSP architecture at baseline 73249aabf9d413325c4a772cd68a3ebc5890415e.

- Issue: #1 — FT-D0 preparation plan and read-only acquisition readiness CLI.
- Branch: claude/ft-d0-preflight; main remains unchanged pending Owner review/merge.
- Mode: PREPARATION_ONLY / LOCAL DEVELOPMENT; no live device access.
- ChatGPT = PO/PM and independent validation; Claude = developer; Owner = business decisions, merge, purchases and deployment.
- Scope authority: Owner instructions -> this control -> current PLAN -> issue acceptance criteria -> implementation/evidence. Do not lower acceptance criteria.
- Allowed now: update scoped project documentation; create tools/ft_data.py, tests and non-sensitive examples; execute stdlib unit tests by PO; commit/push this branch and create a review PR by PO. No automatic issue closure.
- Claude may not edit this control, run shell commands, commit, push, merge, install, read secrets, access networks/devices or authorize a new phase. PO invokes Claude with confined file tools; PO performs validation.
- No new hardware. Existing home MacBook, separate shop network, event recordings on camera memory card. Batch acquisition FIRST, not real-time counting. Software purchase requires a specific proposal; none authorized here.
- The phone can download recordings while at the shop (Owner-reported), NOT evidence of automated retrieval from the home Mac.
- Event clips are non-contiguous; silence does not prove zero traffic; import completeness and detection completeness are different.
- Intended batch storage: temporary videos outside git, bounded storage and retention policy pending approval. No video transfer/access in FT-D0. No video, photos, credentials, private hosts, addresses, serial numbers or personal data in git/evidence.
- No changes to router/camera/network/VPN/OS power/security/authentication, no new schedules/services, no model weights or dependencies, no cloud video transfer, no unrelated repos, no direct main push, no reset/rebase/force push/merge/deploy.
- Production state: UNKNOWN / NOT TOUCHED. No authorization to inspect or change production.
- Stop on unexpected local work or out-of-scope blockers. Finish allowed scope and report blocked steps without claiming PASS.
- Rollback for this task: keep main unchanged; discard/close the review branch only if Owner chooses. No destructive cleanup; no machine configuration migration is performed.
- Next phase FT-D1: secure route evidence + exact camera/firmware/read-only interface + locally configured credentials + bounded storage policy; then list a short date range, fetch ONE approved clip, verify content/time/duration and repeat idempotently. Not authorized in FT-D0.
