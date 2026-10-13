# SD media relay: independent review and PO disposition (OD-46)

Claude advisory completed through the scoped local launcher, exit0/123.4s; no tests/network/runtime access, NOT_RUN_BY_DEVELOPER. PO checked its conclusions against the actual stage results and public sources before writing this final disposition. Raw advisory stays local in launcher results.

## Verified outcome

- Cached auth, selected-device metadata and SD listing work. Playback negotiation (streamType1), pinned TLS and HTTP200 succeeded. Three control parts included an accepted response and structured stream_status finished; no video parts were received in the instrumented trials.
- Increasing initial idle wait, using the negotiated public relay IP with original certificate hostname, and obtaining a fresh playback UID after listing did not resolve the empty-media result for this interval.
- The native-download candidate returned HTTP400 from `/v2/relay/request` with streamType3. **No media connection or download control frame was sent.** Thus the rejection belongs to negotiation; the frame remains untested. Claude's original statement that both variables could explain this400 was incorrect because the second variable never reached the service.
- No valid clip or partial media remains. This is not a successful downloader, a proven Fixed mapping, or proof that the project is impossible.

## Review findings and qualifications

1. Claude correctly distinguished the demonstrated OnTapo playback-shaped cloud path from pytapo's native download packet on a local camera socket. Combining the latter with a relay enum was a hypothesis, not vendor-supported compatibility evidence.
2. The cloud preview and playback packet shapes are different; Claude's original claim that only PTS completion differed was incorrect. This project never sent preview.
3. The observed ACK passed explicit zero error-code validation. No busy refusal was observed; that does not rule out every contention/device-state issue. Changed UID/IP/wait inputs with unchanged results do not prove those factors can never matter.
4. The shortest daily-list interval has no lens label. Primary C545D research says daily search can return one entry per lens, so it may select a PT-only interval. This is a hypothesis to verify, not the cause established by the current tests. `vedio_type`1/2 is validated as an integer but not used to label a lens; playback requests both recording kinds.
5. Fixed marker diagnostics intentionally exclude raw identifiers/URLs/tokens. Claude proposed collecting a full redacted finished reply; PO does **not** authorize dumping raw replies. Any richer capture needs a reviewed field allowlist and synthetic privacy tests first.

## Finite next evidence

- Keep live media trials disabled. No repeated type3 negotiation or blind channel/stream-type sweep.
- Completed the bounded readonly `searchVideoWithUTC` follow-up: actual cloud passthrough returned20rows with lens metadata,19lens1 candidates. Source-backed metadata is now available for selection; this is still not visual Fixed proof or a successful download. The prior unlabeled16second sample is not proven to have been PT-only.
- If another playback trial becomes justified by that evidence, retain only reviewed structural end-reply fields and numeric protocol error codes. Do not log a full reply and redact afterward.
- A complete, duration-validated file and visual Fixed identification are still needed. Owner account input, router changes, paid services and additional hardware are not current prerequisites for this research.

Sources: [OnTapo pinned relay/stream implementation](https://github.com/noriellecruz/ontapo/tree/a387f6abddb72f7e6eea72b374df5ad189da1f5f), [C545D local API research](https://github.com/PeterkoCZ91/tapo-monitoring/blob/d36f0acb7fcc8923886783afaef71404f63c3b0a/docs/tapo-local-api.md), pinned installed pytapo3.4.26 inspected statically only. No upstream SDK or integration tests executed.
